"""Trusted metrics (PHASE_08.md A/B/C; D-064–D-068).

Every figure here is derived from the canonical rows — current invoice revisions, ledgers and
payments — never from a duplicated store. Totals are grouped by currency and never combined.
Periods are tenant-calendar days (Asia/Beirut) with UTC storage. Two views exist and are named
apart: *current state* (what the current revisions say) and *event flow* (what happened when:
confirmation, accepted edit delta, cancellation reversal, dated by the ledger effect).
Historical gross profit uses only each line's sale-time cost snapshot; a line without one is
counted as uncovered, never estimated.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    LedgerEntryType,
    Payment,
    PaymentDirection,
    SupplierLedgerEntry,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.analytics import (
    CurrencyAmount,
    EventFlowResponse,
    EventTotals,
    InvoiceAnalytics,
    MonthlyFlow,
    OverviewResponse,
    PeriodInfo,
    ProfitByCurrency,
)
from tawzeevo_api.services.invoice_editor import money

TENANT_TZ = ZoneInfo("Asia/Beirut")
PERIOD_DAYS = {"30d": 30, "90d": 90, "1y": 365}
ZERO = Decimal("0.0000")


@dataclass(frozen=True)
class Period:
    key: str
    start: datetime | None  # UTC, inclusive; None = all history
    end: datetime  # UTC, exclusive


def resolve_period(key: str, now: datetime | None = None) -> Period:
    """`30d`/`90d`/`1y` = the last N tenant-calendar days including today (D-068); `all`."""
    now_utc = now or datetime.now(UTC)
    if key == "all":
        return Period("all", None, now_utc)
    days = PERIOD_DAYS.get(key)
    if days is None:
        raise AppError(422, "PERIOD_INVALID", "period must be 30d, 90d, 1y or all")
    local_today = now_utc.astimezone(TENANT_TZ).date()
    start_local = datetime.combine(
        local_today - timedelta(days=days - 1), time.min, tzinfo=TENANT_TZ
    )
    return Period(key, start_local.astimezone(UTC), now_utc)


def _in_period(column, period: Period):  # type: ignore[no-untyped-def]
    conditions = [column < period.end]
    if period.start is not None:
        conditions.append(column >= period.start)
    return conditions


def _amounts(rows: dict[str, Decimal]) -> list[CurrencyAmount]:
    return [CurrencyAmount(currency=c, amount=money(v)) for c, v in sorted(rows.items())]


# ---------------------------------------------------------------------------------------------
# Current state
# ---------------------------------------------------------------------------------------------


def invoiced_sales(db: Session, tenant_id: UUID, period: Period) -> dict[str, Decimal]:
    """D-064: current `net_sales` of CONFIRMED invoices confirmed in the period, by currency."""
    rows = db.execute(
        select(InvoiceRevision.currency, func.sum(InvoiceRevision.net_sales))
        .join(Invoice, Invoice.current_revision_id == InvoiceRevision.id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            *_in_period(Invoice.confirmed_at, period),
        )
        .group_by(InvoiceRevision.currency)
    ).all()
    return {currency: Decimal(total or 0) for currency, total in rows}


def customer_receipts(
    db: Session, tenant_id: UUID, period: Period
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """D-065: receipts minus receipt reversals by currency; refunds reported separately."""
    rows = db.execute(
        select(Payment.currency, Payment.direction, func.sum(Payment.amount))
        .where(
            Payment.tenant_id == tenant_id,
            Payment.customer_id.is_not(None),
            *_in_period(Payment.paid_at, period),
        )
        .group_by(Payment.currency, Payment.direction)
    ).all()
    receipts: dict[str, Decimal] = defaultdict(Decimal)
    refunds: dict[str, Decimal] = defaultdict(Decimal)
    for currency, direction, total in rows:
        amount = Decimal(total or 0)
        if direction == PaymentDirection.CUSTOMER_RECEIPT:
            receipts[currency] += amount
        elif direction == PaymentDirection.CUSTOMER_RECEIPT_REVERSAL:
            receipts[currency] -= amount
        elif direction == PaymentDirection.CUSTOMER_REFUND:
            refunds[currency] += amount
    return dict(receipts), dict(refunds)


def _positive_balances(
    rows: list[tuple[str, Decimal]],
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    outstanding: dict[str, Decimal] = defaultdict(Decimal)
    credit: dict[str, Decimal] = defaultdict(Decimal)
    for currency, balance in rows:
        amount = Decimal(balance or 0)
        if amount > 0:
            outstanding[currency] += amount
        elif amount < 0:
            credit[currency] += -amount
    return dict(outstanding), dict(credit)


def customer_outstanding(
    db: Session, tenant_id: UUID
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """D-066: positive customer ledger balances by currency; credits separate, never netted."""
    rows = db.execute(
        select(CustomerLedgerEntry.currency, func.sum(CustomerLedgerEntry.signed_amount))
        .where(CustomerLedgerEntry.tenant_id == tenant_id)
        .group_by(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.currency)
    ).all()
    return _positive_balances([(c, Decimal(b)) for c, b in rows])


def supplier_payable(db: Session, tenant_id: UUID) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    rows = db.execute(
        select(SupplierLedgerEntry.currency, func.sum(SupplierLedgerEntry.signed_amount))
        .where(SupplierLedgerEntry.tenant_id == tenant_id)
        .group_by(SupplierLedgerEntry.supplier_id, SupplierLedgerEntry.currency)
    ).all()
    return _positive_balances([(c, Decimal(b)) for c, b in rows])


def gross_profit(
    db: Session, tenant_id: UUID, period: Period, invoice_id: UUID | None = None
) -> list[ProfitByCurrency]:
    """D-067: Σ (effective_unit_price − unit_cost_snapshot) × quantity over current-revision lines
    of confirmed invoices, per currency, counting only lines whose snapshot exists in the same
    currency and unit; every other line is uncovered. Coverage = covered / all lines."""
    query = (
        select(InvoiceRevisionItem, InvoiceRevision.currency)
        .join(InvoiceRevision, InvoiceRevision.id == InvoiceRevisionItem.invoice_revision_id)
        .join(Invoice, Invoice.current_revision_id == InvoiceRevision.id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            *_in_period(Invoice.confirmed_at, period),
        )
    )
    if invoice_id is not None:
        query = query.where(Invoice.id == invoice_id)
    profit: dict[str, Decimal] = defaultdict(Decimal)
    covered: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for item, currency in db.execute(query).all():
        total[currency] += 1
        if (
            item.unit_cost is None
            or item.cost_currency != currency
            or item.cost_basis is None
            or item.cost_basis != item.price_basis
        ):
            continue  # uncovered: never estimated from a later price
        covered[currency] += 1
        profit[currency] += (
            Decimal(item.effective_unit_price) - Decimal(item.unit_cost)
        ) * Decimal(item.quantity)
    out: list[ProfitByCurrency] = []
    for currency in sorted(total):
        out.append(
            ProfitByCurrency(
                currency=currency,
                gross_profit=money(profit[currency]),
                covered_lines=covered[currency],
                total_lines=total[currency],
                coverage_percent=money(Decimal(covered[currency]) * 100 / Decimal(total[currency]))
                if total[currency]
                else ZERO,
                uncovered_lines=total[currency] - covered[currency],
            )
        )
    return out


def overview(
    db: Session, tenant_id: UUID, period_key: str, now: datetime | None = None
) -> OverviewResponse:
    set_tenant_scope(db, tenant_id)
    period = resolve_period(period_key, now)
    sales = invoiced_sales(db, tenant_id, period)
    receipts, refunds = customer_receipts(db, tenant_id, period)
    outstanding, customer_credit = customer_outstanding(db, tenant_id)
    payable, supplier_credit = supplier_payable(db, tenant_id)
    invoice_count = int(
        db.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.CONFIRMED,
                *_in_period(Invoice.confirmed_at, period),
            )
        )
        or 0
    )
    return OverviewResponse(
        period=PeriodInfo(
            key=period.key, start=period.start, end=period.end, timezone=str(TENANT_TZ)
        ),
        confirmed_invoices=invoice_count,
        invoiced_sales=_amounts(sales),
        customer_receipts=_amounts(receipts),
        customer_refunds=_amounts(refunds),
        customer_outstanding=_amounts(outstanding),
        customer_credit=_amounts(customer_credit),
        supplier_payable=_amounts(payable),
        supplier_credit=_amounts(supplier_credit),
        gross_profit=gross_profit(db, tenant_id, period),
    )


# ---------------------------------------------------------------------------------------------
# Event flow (PHASE_08.md B): dated by the ledger effect, not by the current revision
# ---------------------------------------------------------------------------------------------

_EVENT_TYPES = {
    LedgerEntryType.INVOICE_CHARGE: "confirmations",
    LedgerEntryType.INVOICE_ADJUSTMENT: "edit_deltas",
    LedgerEntryType.INVOICE_REVERSAL: "cancellations",
}


def event_flow(
    db: Session, tenant_id: UUID, period_key: str, now: datetime | None = None
) -> EventFlowResponse:
    set_tenant_scope(db, tenant_id)
    period = resolve_period(period_key, now)
    rows = db.execute(
        select(
            CustomerLedgerEntry.currency,
            CustomerLedgerEntry.entry_type,
            CustomerLedgerEntry.effective_at,
            CustomerLedgerEntry.signed_amount,
        ).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.entry_type.in_(list(_EVENT_TYPES)),
            *_in_period(CustomerLedgerEntry.effective_at, period),
        )
    ).all()
    totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    monthly: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for currency, entry_type, effective_at, amount in rows:
        kind = _EVENT_TYPES[LedgerEntryType(entry_type)]
        totals[currency][kind] += Decimal(amount)
        month = effective_at.astimezone(TENANT_TZ).strftime("%Y-%m")
        monthly[(currency, month)] += Decimal(amount)
    return EventFlowResponse(
        period=PeriodInfo(
            key=period.key, start=period.start, end=period.end, timezone=str(TENANT_TZ)
        ),
        totals=[
            EventTotals(
                currency=currency,
                confirmations=money(kinds["confirmations"]),
                edit_deltas=money(kinds["edit_deltas"]),
                cancellations=money(kinds["cancellations"]),
                net_effect=money(
                    kinds["confirmations"] + kinds["edit_deltas"] + kinds["cancellations"]
                ),
            )
            for currency, kinds in sorted(totals.items())
        ],
        monthly=[
            MonthlyFlow(currency=currency, month=month, net_effect=money(amount))
            for (currency, month), amount in sorted(monthly.items())
        ],
    )


def invoice_analytics(db: Session, tenant_id: UUID, invoice_id: UUID) -> InvoiceAnalytics:
    set_tenant_scope(db, tenant_id)
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.tenant_id != tenant_id:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    revision = db.get(InvoiceRevision, invoice.current_revision_id)
    charge = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.source_effect_key == f"invoice:{invoice.id}:charge",
        )
    )
    from tawzeevo_api.services.delivery import amount_to_collect

    collected = ZERO
    if charge is not None:
        remaining = amount_to_collect(db, tenant_id, invoice)
        collected = money(Decimal(charge.signed_amount) - remaining)
    profit = gross_profit(
        db, tenant_id, Period("all", None, datetime.now(UTC)), invoice_id=invoice.id
    )
    return InvoiceAnalytics(
        invoice_id=invoice.id,
        status=invoice.status.value,
        currency=revision.currency if revision else "USD",
        net_sales=money(revision.net_sales) if revision else ZERO,
        discount_total=money(revision.discount_total) if revision else ZERO,
        markup_total=money(revision.markup_total) if revision else ZERO,
        receipts_applied=collected,
        outstanding=money(Decimal(charge.signed_amount) - collected) if charge else ZERO,
        gross_profit=profit[0] if profit else None,
        confirmed_at=invoice.confirmed_at,
        cancelled_at=invoice.cancelled_at,
    )
