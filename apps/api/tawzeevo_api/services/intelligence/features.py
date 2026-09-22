"""Shared customer feature layer (D-089): one batched pass per tenant, keyed by customer + currency.

Semantics are the established ones, reused rather than re-derived:
- sales are the current revision's `net_sales` of CONFIRMED invoices, dated by `confirmed_at`,
  attributed by the owner-resolved `Invoice.customer_id` (D-064, D-072);
- windows are tenant-calendar days from `analytics.resolve_period` (D-068);
- receipts are receipts minus receipt reversals by `paid_at`; refunds stay separate (D-065);
- balance, oldest unpaid obligation, overdue age and overdue flag come from
  `customer_ledger.customer_debts` (D-040), so they reconcile by construction.

`as_of` is fixed once per call and is the evaluation clock: invoices confirmed after it are
ignored, windows end at it, and overdue age is measured to it. Ledger balances are the current
state, exactly as the ledger service reports them.

Deliberately absent (see the implementation notes): customer margin (D-067 is not a net-margin
measure) and any late-payment proxy (allocation timing follows FIFO policy, not customer intent,
so no trustworthy per-customer lateness can be derived without due dates).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceStatus,
    LedgerEntryType,
    OrderCancellationRequest,
    Payment,
    PaymentDirection,
    TenantFinancialSettings,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.analytics import resolve_period
from tawzeevo_api.services.customer_ledger import customer_debts, overdue_calendar_date
from tawzeevo_api.services.invoice_editor import money

ZERO = Decimal("0.0000")
# Cadence needs at least this many confirmed invoices (two intervals) in one currency.
MIN_INVOICES_FOR_CADENCE = 3
# "Recent" friction window (tenant-calendar days, via resolve_period).
FRICTION_PERIOD = "30d"


@dataclass(frozen=True)
class CustomerCurrencyFeatures:
    customer_id: UUID
    customer_name: str
    customer_grade: str | None
    currency: str
    as_of: datetime
    # purchase behaviour
    invoice_count_lifetime: int
    invoice_count_30d: int
    invoice_count_90d: int
    sales_30d: Decimal
    sales_90d: Decimal
    sales_365d: Decimal
    average_invoice_value: Decimal | None
    first_purchase_at: datetime | None
    last_purchase_at: datetime | None
    days_since_last_purchase: int | None
    median_purchase_interval_days: Decimal | None
    purchase_interval_mad_days: Decimal | None
    history_sufficient: bool
    recency_ratio: Decimal | None
    recent_activity_ratio: Decimal | None
    # receivables
    balance: Decimal
    outstanding_balance: Decimal
    oldest_unpaid_at: datetime | None
    overdue_age_days: int | None
    overdue_threshold_days: int | None
    is_overdue: bool
    receipts_30d: Decimal
    receipts_90d: Decimal
    # friction in the last FRICTION_PERIOD
    recent_cancelled_invoices: int
    recent_receipt_reversals: int
    recent_negative_adjustments: int
    recent_cancellation_requests: int
    recent_refunds: Decimal


@dataclass
class _Acc:
    dates: list[datetime] = field(default_factory=list)
    amounts: list[Decimal] = field(default_factory=list)


def _days_between(later: datetime, earlier: datetime) -> int:
    return (overdue_calendar_date(later) - overdue_calendar_date(earlier)).days


def _mad(values: list[Decimal], center: Decimal) -> Decimal:
    return Decimal(median([abs(v - center) for v in values]))


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return (numerator / denominator).quantize(Decimal("0.0001"))


def cadence(
    dates: list[datetime], as_of: datetime
) -> tuple[Decimal | None, Decimal | None, bool, Decimal | None]:
    """Median/MAD of tenant-calendar purchase intervals and the recency ratio.

    Eligible only with >= MIN_INVOICES_FOR_CADENCE purchases and a positive median interval
    (several purchases on one day must not divide by zero)."""
    if len(dates) < MIN_INVOICES_FOR_CADENCE:
        return None, None, False, None
    ordered = sorted(dates)
    intervals = [
        Decimal(_days_between(later, earlier))
        for earlier, later in zip(ordered, ordered[1:], strict=False)
    ]
    mid = Decimal(median(intervals))
    mad = _mad(intervals, mid)
    if mid <= 0:
        return mid, mad, False, None
    days_since = Decimal(_days_between(as_of, ordered[-1]))
    return mid, mad, True, _ratio(days_since, mid)


def _period_start(key: str, as_of: datetime) -> datetime:
    start = resolve_period(key, as_of).start
    assert start is not None
    return start


def customer_features(
    db: Session, tenant_id: UUID, *, as_of: datetime | None = None
) -> list[CustomerCurrencyFeatures]:
    """Features for every customer/currency pair with a confirmed purchase or a ledger balance.

    Read-only: no flush, no commit. Deterministically ordered by (currency, customer name, id)."""
    as_of = as_of or datetime.now(UTC)
    set_tenant_scope(db, tenant_id)
    start_30 = _period_start("30d", as_of)
    start_90 = _period_start("90d", as_of)
    start_365 = _period_start("1y", as_of)
    friction_start = _period_start(FRICTION_PERIOD, as_of)

    customers = {
        row.id: row for row in db.scalars(select(Customer).where(Customer.tenant_id == tenant_id))
    }
    settings = db.get(TenantFinancialSettings, tenant_id)
    threshold = settings.customer_overdue_threshold_days if settings is not None else None

    purchases: dict[tuple[UUID, str], _Acc] = defaultdict(_Acc)
    for customer_id, confirmed_at, currency, net_sales in db.execute(
        select(
            Invoice.customer_id,
            Invoice.confirmed_at,
            InvoiceRevision.currency,
            InvoiceRevision.net_sales,
        )
        .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.customer_id.is_not(None),
            Invoice.confirmed_at.is_not(None),
            Invoice.confirmed_at <= as_of,
        )
        .order_by(Invoice.confirmed_at.asc(), Invoice.id.asc())
    ).all():
        acc = purchases[(customer_id, currency)]
        acc.dates.append(confirmed_at)
        acc.amounts.append(Decimal(net_sales))

    balances: dict[tuple[UUID, str], Decimal] = {
        (customer_id, currency): money(Decimal(total or 0))
        for customer_id, currency, total in db.execute(
            select(
                CustomerLedgerEntry.customer_id,
                CustomerLedgerEntry.currency,
                func.sum(CustomerLedgerEntry.signed_amount),
            )
            .where(CustomerLedgerEntry.tenant_id == tenant_id)
            .group_by(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.currency)
        ).all()
    }
    debts = {(d.customer_id, d.currency): d for d in customer_debts(db, tenant_id, now=as_of).debts}

    receipts_30: dict[tuple[UUID, str], Decimal] = defaultdict(Decimal)
    receipts_90: dict[tuple[UUID, str], Decimal] = defaultdict(Decimal)
    refunds_recent: dict[tuple[UUID, str], Decimal] = defaultdict(Decimal)
    reversals_recent: dict[tuple[UUID, str], int] = defaultdict(int)
    for customer_id, currency, direction, amount, paid_at in db.execute(
        select(
            Payment.customer_id,
            Payment.currency,
            Payment.direction,
            Payment.amount,
            Payment.paid_at,
        ).where(
            Payment.tenant_id == tenant_id,
            Payment.customer_id.is_not(None),
            Payment.paid_at >= start_90,
            Payment.paid_at < as_of,
        )
    ).all():
        key = (customer_id, currency)
        value = Decimal(amount)
        if direction == PaymentDirection.CUSTOMER_RECEIPT_REVERSAL:
            value = -value
            if paid_at >= friction_start:
                reversals_recent[key] += 1
        elif direction == PaymentDirection.CUSTOMER_REFUND:
            if paid_at >= friction_start:
                refunds_recent[key] += value
            continue
        elif direction != PaymentDirection.CUSTOMER_RECEIPT:
            continue
        receipts_90[key] += value
        if paid_at >= start_30:
            receipts_30[key] += value

    cancelled: dict[tuple[UUID, str], int] = defaultdict(int)
    for customer_id, currency, count in db.execute(
        select(Invoice.customer_id, InvoiceRevision.currency, func.count())
        .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.CANCELLED,
            Invoice.customer_id.is_not(None),
            Invoice.cancelled_at >= friction_start,
            Invoice.cancelled_at < as_of,
        )
        .group_by(Invoice.customer_id, InvoiceRevision.currency)
    ).all():
        cancelled[(customer_id, currency)] = int(count)

    negative_adjustments: dict[tuple[UUID, str], int] = defaultdict(int)
    for customer_id, currency, count in db.execute(
        select(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.currency, func.count())
        .where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.entry_type == LedgerEntryType.INVOICE_ADJUSTMENT,
            CustomerLedgerEntry.signed_amount < 0,
            CustomerLedgerEntry.effective_at >= friction_start,
            CustomerLedgerEntry.effective_at < as_of,
        )
        .group_by(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.currency)
    ).all():
        negative_adjustments[(customer_id, currency)] = int(count)

    requests: dict[tuple[UUID, str], int] = defaultdict(int)
    for customer_id, currency, count in db.execute(
        select(Invoice.customer_id, InvoiceRevision.currency, func.count())
        .select_from(OrderCancellationRequest)
        .join(Invoice, Invoice.order_id == OrderCancellationRequest.order_id)
        .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
        .where(
            OrderCancellationRequest.tenant_id == tenant_id,
            Invoice.tenant_id == tenant_id,
            Invoice.customer_id.is_not(None),
            OrderCancellationRequest.created_at >= friction_start,
            OrderCancellationRequest.created_at < as_of,
        )
        .group_by(Invoice.customer_id, InvoiceRevision.currency)
    ).all():
        requests[(customer_id, currency)] = int(count)

    keys = set(purchases) | {key for key, value in balances.items() if value != 0}
    out: list[CustomerCurrencyFeatures] = []
    for customer_id, currency in keys:
        customer = customers.get(customer_id)
        if customer is None:
            continue
        acc = purchases.get((customer_id, currency), _Acc())
        pairs = list(zip(acc.dates, acc.amounts, strict=True))
        count = len(pairs)
        sales_30 = sum((a for d, a in pairs if d >= start_30), ZERO)
        sales_90 = sum((a for d, a in pairs if d >= start_90), ZERO)
        sales_365 = sum((a for d, a in pairs if d >= start_365), ZERO)
        first = acc.dates[0] if acc.dates else None
        last = acc.dates[-1] if acc.dates else None
        mid, mad, sufficient, recency = cadence(acc.dates, as_of)
        # 30d activity against the average 30-day block of the 90d window; only meaningful
        # when the customer was already buying before the 90d window opened.
        activity: Decimal | None = None
        if first is not None and first < start_90 and sales_90 > 0:
            activity = _ratio(sales_30 * 3, sales_90)
        balance = balances.get((customer_id, currency), ZERO)
        debt = debts.get((customer_id, currency))
        key = (customer_id, currency)
        out.append(
            CustomerCurrencyFeatures(
                customer_id=customer_id,
                customer_name=customer.name,
                customer_grade=customer.grade.value if customer.grade else None,
                currency=currency,
                as_of=as_of,
                invoice_count_lifetime=count,
                invoice_count_30d=sum(1 for d, _ in pairs if d >= start_30),
                invoice_count_90d=sum(1 for d, _ in pairs if d >= start_90),
                sales_30d=money(sales_30),
                sales_90d=money(sales_90),
                sales_365d=money(sales_365),
                average_invoice_value=money(sum(acc.amounts, ZERO) / count) if count else None,
                first_purchase_at=first,
                last_purchase_at=last,
                days_since_last_purchase=_days_between(as_of, last) if last else None,
                median_purchase_interval_days=mid,
                purchase_interval_mad_days=mad,
                history_sufficient=sufficient,
                recency_ratio=recency,
                recent_activity_ratio=activity,
                balance=balance,
                outstanding_balance=max(ZERO, balance),
                oldest_unpaid_at=debt.oldest_unpaid_at if debt else None,
                overdue_age_days=debt.overdue_age_days if debt else None,
                overdue_threshold_days=threshold,
                is_overdue=bool(debt and debt.is_overdue),
                receipts_30d=money(receipts_30[key]),
                receipts_90d=money(receipts_90[key]),
                recent_cancelled_invoices=cancelled[key],
                recent_receipt_reversals=reversals_recent[key],
                recent_negative_adjustments=negative_adjustments[key],
                recent_cancellation_requests=requests[key],
                recent_refunds=money(refunds_recent[key]),
            )
        )
    out.sort(key=lambda f: (f.currency, f.customer_name.casefold(), str(f.customer_id)))
    return out
