"""Cash-flow position and ageing (D-089) — a composition of existing figures, never a forecast.

Tawzeevo has no bank/cash accounts, customer due dates, supplier terms or FX, so this reports only:
current receivables and payables (the analytics/ledger services' own figures), overdue receivables
(D-040), receivables aged by their oldest unpaid obligation, historical receipts/refunds/supplier
payments over a supported period, and the planned delivery collections that open delivery tasks
already carry — labelled as a projection because `amount_to_collect` ignores invoice adjustments.
Per currency only; nothing is converted or combined.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import DeliveryTask, DeliveryTaskStatus, Payment, PaymentDirection
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services import analytics
from tawzeevo_api.services.customer_ledger import (
    customer_debts,
    get_financial_settings,
    overdue_calendar_date,
)
from tawzeevo_api.services.invoice_editor import money

ZERO = Decimal("0.0000")
# Age of the oldest unpaid obligation (days since its ledger effect), not contractual due dates.
AGEING_BUCKETS = (
    ("AGE_0_30", 0, 30),
    ("AGE_31_60", 31, 60),
    ("AGE_61_90", 61, 90),
    ("AGE_91_PLUS", 91, None),
)
AGE_UNKNOWN = "AGE_UNKNOWN"  # positive balance with no unpaid obligation date (e.g. a refund)
DEFAULT_PLANNED_DAYS = 7
MAX_PLANNED_DAYS = 31
PLANNED_SOURCE = "DELIVERY_TASK_AMOUNT_TO_COLLECT"
PLANNED_WARNING = "DELIVERY_PROJECTION_IGNORES_ADJUSTMENTS"


@dataclass(frozen=True)
class AgeingBucket:
    bucket: str
    amount: Decimal
    customer_count: int


@dataclass(frozen=True)
class PlannedCollections:
    amount: Decimal
    task_count: int
    from_date: date
    through_date: date
    source: str = PLANNED_SOURCE
    projection_warning_code: str = PLANNED_WARNING


@dataclass(frozen=True)
class CurrencyCashFlow:
    currency: str
    customer_receivables: Decimal
    customer_credit: Decimal
    overdue_receivables: Decimal
    overdue_customer_count: int
    supplier_payables: Decimal
    supplier_credit: Decimal
    ageing: list[AgeingBucket]
    customer_receipts: Decimal
    customer_refunds: Decimal
    supplier_payments: Decimal
    net_customer_collections: Decimal
    average_weekly_collections: Decimal | None
    planned_collections: PlannedCollections


@dataclass(frozen=True)
class CashFlowReport:
    as_of: datetime
    period: analytics.Period
    overdue_threshold_days: int | None
    currencies: list[CurrencyCashFlow]


def _bucket(age: int | None) -> str:
    if age is None:
        return AGE_UNKNOWN
    for name, low, high in AGEING_BUCKETS:
        if age >= low and (high is None or age <= high):
            return name
    return AGE_UNKNOWN


def supplier_payments(db: Session, tenant_id: UUID, period: analytics.Period) -> dict[str, Decimal]:
    """Supplier payments minus their reversals by `paid_at`, mirroring D-065 for customers."""
    rows = db.execute(
        select(Payment.currency, Payment.direction, func.sum(Payment.amount))
        .where(
            Payment.tenant_id == tenant_id,
            Payment.supplier_id.is_not(None),
            Payment.direction.in_(
                [PaymentDirection.SUPPLIER_PAYMENT, PaymentDirection.SUPPLIER_PAYMENT_REVERSAL]
            ),
            Payment.paid_at < period.end,
            *([Payment.paid_at >= period.start] if period.start is not None else []),
        )
        .group_by(Payment.currency, Payment.direction)
    ).all()
    out: dict[str, Decimal] = defaultdict(Decimal)
    for currency, direction, total in rows:
        sign = 1 if direction == PaymentDirection.SUPPLIER_PAYMENT else -1
        out[currency] += sign * Decimal(total or 0)
    return dict(out)


def cash_flow(
    db: Session,
    tenant_id: UUID,
    period_key: str = "90d",
    *,
    planned_days: int = DEFAULT_PLANNED_DAYS,
    as_of: datetime | None = None,
) -> CashFlowReport:
    as_of = as_of or datetime.now(UTC)
    planned_days = max(1, min(MAX_PLANNED_DAYS, planned_days))
    set_tenant_scope(db, tenant_id)
    period = analytics.resolve_period(period_key, as_of)

    receivables, customer_credit = analytics.customer_outstanding(db, tenant_id)
    payables, supplier_credit = analytics.supplier_payable(db, tenant_id)
    receipts, refunds = analytics.customer_receipts(db, tenant_id, period)
    paid_suppliers = supplier_payments(db, tenant_id, period)

    debts = customer_debts(db, tenant_id, now=as_of).debts
    threshold = get_financial_settings(db, tenant_id).customer_overdue_threshold_days
    overdue: dict[str, Decimal] = defaultdict(Decimal)
    overdue_count: dict[str, int] = defaultdict(int)
    ageing: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    ageing_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for debt in debts:
        if debt.is_overdue:
            overdue[debt.currency] += debt.balance
            overdue_count[debt.currency] += 1
        bucket = _bucket(debt.overdue_age_days)
        ageing[debt.currency][bucket] += debt.balance
        ageing_count[debt.currency][bucket] += 1

    today = overdue_calendar_date(as_of)
    through = today + timedelta(days=planned_days - 1)
    planned: dict[str, Decimal] = defaultdict(Decimal)
    planned_count: dict[str, int] = defaultdict(int)
    for currency, total, count in db.execute(
        select(DeliveryTask.currency, func.sum(DeliveryTask.amount_to_collect), func.count())
        .where(
            DeliveryTask.tenant_id == tenant_id,
            DeliveryTask.status == DeliveryTaskStatus.ASSIGNED.value,
            DeliveryTask.delivery_date >= today,
            DeliveryTask.delivery_date <= through,
        )
        .group_by(DeliveryTask.currency)
    ).all():
        planned[currency] = Decimal(total or 0)
        planned_count[currency] = int(count)

    weeks: Decimal | None = None
    if period.start is not None:
        weeks = Decimal((period.end - period.start).total_seconds()) / Decimal(7 * 86400)

    currencies = sorted(
        set(receivables)
        | set(customer_credit)
        | set(payables)
        | set(supplier_credit)
        | set(receipts)
        | set(refunds)
        | set(paid_suppliers)
        | set(planned)
    )
    out: list[CurrencyCashFlow] = []
    for currency in currencies:
        net = receipts.get(currency, ZERO) - refunds.get(currency, ZERO)
        buckets = [
            AgeingBucket(name, money(ageing[currency][name]), ageing_count[currency][name])
            for name in [b[0] for b in AGEING_BUCKETS] + [AGE_UNKNOWN]
            if name != AGE_UNKNOWN or ageing_count[currency][name]
        ]
        out.append(
            CurrencyCashFlow(
                currency=currency,
                customer_receivables=money(receivables.get(currency, ZERO)),
                customer_credit=money(customer_credit.get(currency, ZERO)),
                overdue_receivables=money(overdue[currency]),
                overdue_customer_count=overdue_count[currency],
                supplier_payables=money(payables.get(currency, ZERO)),
                supplier_credit=money(supplier_credit.get(currency, ZERO)),
                ageing=buckets,
                customer_receipts=money(receipts.get(currency, ZERO)),
                customer_refunds=money(refunds.get(currency, ZERO)),
                supplier_payments=money(paid_suppliers.get(currency, ZERO)),
                net_customer_collections=money(net),
                average_weekly_collections=money(net / weeks) if weeks else None,
                planned_collections=PlannedCollections(
                    amount=money(planned[currency]),
                    task_count=planned_count[currency],
                    from_date=today,
                    through_date=through,
                ),
            )
        )
    return CashFlowReport(
        as_of=as_of, period=period, overdue_threshold_days=threshold, currencies=out
    )
