"""Business anomaly detection (D-089): deterministic rules and robust baselines, stateless.

An anomaly is an unusual value compared with the tenant's own history — never an accusation and
never a cause. Tenant-level series use 7-day tenant-calendar blocks (Asia/Beirut): the current
block is the last 7 days including today (as D-068 counts periods), compared with up to
BASELINE_BLOCKS preceding blocks using the median and median absolute deviation (MAD). A series
is only evaluated once MIN_BASELINE_BLOCKS whole blocks lie after the currency's first activity;
otherwise it is reported as insufficient history, not as an anomaly. Everything is per currency.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    Customer,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    Payment,
    PaymentDirection,
    SupplierLedgerEntry,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.customer_ledger import (
    OVERDUE_CALENDAR,
    customer_debts,
    overdue_calendar_date,
)
from tawzeevo_api.services.invoice_editor import money

# ---- centralized thresholds (boundary-tested; adjustable without schema changes)
BLOCK_DAYS = 7
BASELINE_BLOCKS = 8
MIN_BASELINE_BLOCKS = 6
MAD_TO_SIGMA = Decimal("1.4826")
WATCH_Z = Decimal("3")
HIGH_Z = Decimal("5")
SCALE_FLOOR_FRACTION = Decimal("0.10")  # scale never below 10% of the baseline median
COUNT_SCALE_FLOOR = Decimal("1")  # event counts: a deviation of one event is the minimum unit
MIN_SPIKE_EVENTS = 3
MIN_REFUND_EVENTS = 2
CUSTOMER_MIN_PRIOR_INVOICES = 5
CUSTOMER_MIN_MULTIPLE = Decimal("2")  # and at least twice the customer's median invoice
BACKDATE_MIN_DAYS = 7
BACKDATE_MIN_PRIOR_RECEIPTS = 5
BACKDATE_MIN_MULTIPLE = Decimal("2")  # at least twice the median receipt of the prior 90 days
BACKDATE_HISTORY_DAYS = 90
OVERDUE_CROSSING_DAYS = BLOCK_DAYS

ANOMALY_TYPES = (
    "SALES_PERIOD_HIGH",
    "SALES_PERIOD_LOW",
    "CANCELLATION_SPIKE",
    "REVERSAL_SPIKE",
    "REFUND_SPIKE",
    "CUSTOMER_INVOICE_VALUE_HIGH",
    "BACKDATED_RECEIPT_LARGE",
    "OVERDUE_THRESHOLD_CROSSED",
    "SUPPLIER_PAYABLE_JUMP",
    "LINE_PRICE_BELOW_SNAPSHOT_COST",
)
_SEVERITY_ORDER = {"HIGH": 0, "WATCH": 1, "INFO": 2}

Detail = Decimal | int | str | bool | None


@dataclass(frozen=True)
class Baseline:
    method: str  # MEDIAN_MAD | DIRECT_RULE
    median: Decimal | None = None
    mad: Decimal | None = None
    sample_size: int | None = None


@dataclass(frozen=True)
class Anomaly:
    type: str
    severity: str
    currency: str
    subject_type: str  # TENANT | CUSTOMER | INVOICE | SUPPLIER
    subject_id: UUID | None
    metric: str
    observed_value: Decimal
    baseline: Baseline
    reason_code: str
    details: Mapping[str, Detail] = field(default_factory=dict)


@dataclass(frozen=True)
class AnomalyWindow:
    start: datetime  # UTC, inclusive: local midnight BLOCK_DAYS-1 days before today
    end: datetime  # as_of


@dataclass(frozen=True)
class AnomalyReport:
    as_of: datetime
    window: AnomalyWindow
    anomalies: dict[str, list[Anomaly]]  # by currency
    insufficient_history: dict[str, list[str]]  # currency -> anomaly families not evaluated


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def robust_z(
    current: Decimal, baseline: list[Decimal], *, count_series: bool = False
) -> tuple[Decimal, Decimal, Decimal | None]:
    """(median, MAD, z) with a floored scale.

    Counts never scale below one event. A money series whose median and MAD are both zero (e.g.
    sporadic supplier activity) falls back to the mean absolute baseline value; z is None only when
    the whole baseline is zero."""
    mid = Decimal(median(baseline))
    mad = Decimal(median([abs(v - mid) for v in baseline]))
    scale = max(MAD_TO_SIGMA * mad, SCALE_FLOOR_FRACTION * abs(mid))
    if count_series:
        scale = max(scale, COUNT_SCALE_FLOOR)
    elif scale <= 0 and baseline:
        scale = sum((abs(v) for v in baseline), Decimal(0)) / len(baseline)
    if scale <= 0:
        return mid, mad, None
    return mid, mad, (current - mid) / scale


def _severity(z: Decimal) -> str | None:
    magnitude = abs(z)
    if magnitude >= HIGH_Z:
        return "HIGH"
    if magnitude >= WATCH_Z:
        return "WATCH"
    return None


def _block(local_day: date, today: date) -> int | None:
    offset = (today - local_day).days
    if offset < 0:
        return None
    index = offset // BLOCK_DAYS
    return index if index <= BASELINE_BLOCKS else None


def _covered_blocks(first_day: date | None, today: date) -> list[int]:
    """Baseline block indexes lying wholly on or after the first day of activity."""
    if first_day is None:
        return []
    return [
        b
        for b in range(1, BASELINE_BLOCKS + 1)
        if first_day <= today - timedelta(days=BLOCK_DAYS * b + BLOCK_DAYS - 1)
    ]


class _Series:
    """Per-currency 7-day block sums."""

    def __init__(self) -> None:
        self.values: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        self.counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    def add(self, currency: str, when: datetime, value: Decimal, today: date) -> None:
        block = _block(overdue_calendar_date(when), today)
        if block is None:
            return
        self.values[currency][block] += value
        self.counts[currency][block] += 1


def _block_check(
    *, series: _Series, currency: str, blocks: list[int], use_counts: bool
) -> tuple[Decimal, int, Baseline, Decimal | None]:
    if use_counts:
        current = Decimal(series.counts[currency][0])
        baseline = [Decimal(series.counts[currency][b]) for b in blocks]
    else:
        current = series.values[currency][0]
        baseline = [series.values[currency][b] for b in blocks]
    mid, mad, z = robust_z(current, baseline, count_series=use_counts)
    return (
        current,
        series.counts[currency][0],
        Baseline("MEDIAN_MAD", _q(mid), _q(mad), len(baseline)),
        z,
    )


def _local_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=OVERDUE_CALENDAR).astimezone(UTC)


def detect_anomalies(
    db: Session,
    tenant_id: UUID,
    *,
    as_of: datetime | None = None,
    types: Iterable[str] | None = None,
) -> AnomalyReport:
    as_of = as_of or datetime.now(UTC)
    wanted = set(types) if types is not None else set(ANOMALY_TYPES)
    set_tenant_scope(db, tenant_id)
    today = overdue_calendar_date(as_of)
    window_start = _local_midnight(today - timedelta(days=BLOCK_DAYS - 1))
    series_start = _local_midnight(today - timedelta(days=BLOCK_DAYS * (BASELINE_BLOCKS + 1) - 1))
    found: dict[str, list[Anomaly]] = defaultdict(list)
    insufficient: dict[str, set[str]] = defaultdict(set)
    names = {
        row.id: row.name
        for row in db.scalars(select(Customer).where(Customer.tenant_id == tenant_id))
    }

    # ---- activity start per currency: first confirmed invoice (the business traded in it)
    first_sale: dict[str, date] = {
        currency: overdue_calendar_date(first)
        for currency, first in db.execute(
            select(InvoiceRevision.currency, func.min(Invoice.confirmed_at))
            .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.confirmed_at.is_not(None),
                Invoice.status.in_([InvoiceStatus.CONFIRMED, InvoiceStatus.CANCELLED]),
            )
            .group_by(InvoiceRevision.currency)
        ).all()
        if first is not None
    }

    def report(
        anomaly_type: str,
        currency: str,
        current: Decimal,
        baseline: Baseline,
        z: Decimal | None,
        metric: str,
        high_only: bool = True,
        **details: Detail,
    ) -> None:
        if z is None:
            return
        severity = _severity(z)
        if severity is None or (high_only and z < 0):
            return
        found[currency].append(
            Anomaly(
                type=anomaly_type,
                severity=severity,
                currency=currency,
                subject_type="TENANT",
                subject_id=None,
                metric=metric,
                observed_value=_q(current),
                baseline=baseline,
                reason_code="ABOVE_BASELINE" if z > 0 else "BELOW_BASELINE",
                details={"robust_z": _q(z), **details},
            )
        )

    # ---- confirmed sales per block (current revisions, D-064)
    if wanted & {"SALES_PERIOD_HIGH", "SALES_PERIOD_LOW"}:
        sales = _Series()
        for currency, confirmed_at, net in db.execute(
            select(InvoiceRevision.currency, Invoice.confirmed_at, InvoiceRevision.net_sales)
            .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.confirmed_at >= series_start,
                Invoice.confirmed_at <= as_of,
            )
        ).all():
            sales.add(currency, confirmed_at, Decimal(net), today)
        for currency in sorted(first_sale):
            blocks = _covered_blocks(first_sale[currency], today)
            if len(blocks) < MIN_BASELINE_BLOCKS:
                insufficient[currency].add("SALES_PERIOD")
                continue
            current, events, baseline, z = _block_check(
                series=sales, currency=currency, blocks=blocks, use_counts=False
            )
            if z is None:
                continue
            kind = "SALES_PERIOD_HIGH" if z > 0 else "SALES_PERIOD_LOW"
            if kind in wanted:
                report(
                    kind,
                    currency,
                    money(current),
                    baseline,
                    z,
                    "confirmed_sales_7d",
                    high_only=False,
                    invoice_count=events,
                )

    # ---- cancellation / receipt-reversal counts and refund values per block
    if wanted & {"CANCELLATION_SPIKE", "REVERSAL_SPIKE", "REFUND_SPIKE"}:
        cancellations = _Series()
        for currency, cancelled_at in db.execute(
            select(InvoiceRevision.currency, Invoice.cancelled_at)
            .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.CANCELLED,
                Invoice.cancelled_at >= series_start,
                Invoice.cancelled_at <= as_of,
            )
        ).all():
            cancellations.add(currency, cancelled_at, Decimal(1), today)
        reversals = _Series()
        refunds = _Series()
        for currency, direction, amount, paid_at in db.execute(
            select(Payment.currency, Payment.direction, Payment.amount, Payment.paid_at).where(
                Payment.tenant_id == tenant_id,
                Payment.customer_id.is_not(None),
                Payment.direction.in_(
                    [PaymentDirection.CUSTOMER_RECEIPT_REVERSAL, PaymentDirection.CUSTOMER_REFUND]
                ),
                Payment.paid_at >= series_start,
                Payment.paid_at <= as_of,
            )
        ).all():
            target = (
                reversals if direction == PaymentDirection.CUSTOMER_RECEIPT_REVERSAL else refunds
            )
            target.add(currency, paid_at, Decimal(amount), today)
        for kind, series, use_counts, minimum, metric in (
            ("CANCELLATION_SPIKE", cancellations, True, MIN_SPIKE_EVENTS, "cancelled_invoices_7d"),
            ("REVERSAL_SPIKE", reversals, True, MIN_SPIKE_EVENTS, "receipt_reversals_7d"),
            ("REFUND_SPIKE", refunds, False, MIN_REFUND_EVENTS, "customer_refunds_7d"),
        ):
            if kind not in wanted:
                continue
            for currency in sorted(first_sale):
                blocks = _covered_blocks(first_sale[currency], today)
                if len(blocks) < MIN_BASELINE_BLOCKS:
                    insufficient[currency].add(kind)
                    continue
                current, events, baseline, z = _block_check(
                    series=series, currency=currency, blocks=blocks, use_counts=use_counts
                )
                if events < minimum:
                    continue
                report(kind, currency, current, baseline, z, metric, event_count=events)

    # ---- unusually large invoice for one customer (same customer + currency only)
    if "CUSTOMER_INVOICE_VALUE_HIGH" in wanted:
        history: dict[tuple[UUID, str], list[tuple[datetime, UUID, Decimal]]] = defaultdict(list)
        for customer_id, invoice_id, confirmed_at, currency, net in db.execute(
            select(
                Invoice.customer_id,
                Invoice.id,
                Invoice.confirmed_at,
                InvoiceRevision.currency,
                InvoiceRevision.net_sales,
            )
            .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.customer_id.is_not(None),
                Invoice.confirmed_at <= as_of,
            )
            .order_by(Invoice.confirmed_at.asc(), Invoice.id.asc())
        ).all():
            history[(customer_id, currency)].append((confirmed_at, invoice_id, Decimal(net)))
        for (customer_id, currency), rows in history.items():
            for index, (confirmed_at, invoice_id, value) in enumerate(rows):
                if confirmed_at < window_start:
                    continue
                prior = [v for _at, _id, v in rows[:index]]
                if len(prior) < CUSTOMER_MIN_PRIOR_INVOICES:
                    continue
                mid, mad, z = robust_z(value, prior)
                if z is None or value < CUSTOMER_MIN_MULTIPLE * mid:
                    continue
                severity = _severity(z)
                if severity is None or z < 0:
                    continue
                found[currency].append(
                    Anomaly(
                        type="CUSTOMER_INVOICE_VALUE_HIGH",
                        severity=severity,
                        currency=currency,
                        subject_type="INVOICE",
                        subject_id=invoice_id,
                        metric="invoice_net_sales",
                        observed_value=money(value),
                        baseline=Baseline("MEDIAN_MAD", _q(mid), _q(mad), len(prior)),
                        reason_code="ABOVE_CUSTOMER_HISTORY",
                        details={
                            "customer_id": str(customer_id),
                            "customer_name": names.get(customer_id),
                            "robust_z": _q(z),
                        },
                    )
                )

    # ---- receipts recorded well after their payment date (Payment.recorded_at vs paid_at)
    if "BACKDATED_RECEIPT_LARGE" in wanted:
        receipts = (
            db.execute(
                select(Payment)
                .where(
                    Payment.tenant_id == tenant_id,
                    Payment.customer_id.is_not(None),
                    Payment.direction == PaymentDirection.CUSTOMER_RECEIPT,
                    Payment.recorded_at >= window_start - timedelta(days=BACKDATE_HISTORY_DAYS),
                    Payment.recorded_at <= as_of,
                )
                .order_by(Payment.recorded_at.asc(), Payment.id.asc())
            )
            .scalars()
            .all()
        )
        for payment in receipts:
            if payment.recorded_at < window_start:
                continue
            lag = (
                overdue_calendar_date(payment.recorded_at) - overdue_calendar_date(payment.paid_at)
            ).days
            if lag < BACKDATE_MIN_DAYS:
                continue
            prior = [
                Decimal(p.amount)
                for p in receipts
                if p.currency == payment.currency
                and p.id != payment.id
                and payment.recorded_at - timedelta(days=BACKDATE_HISTORY_DAYS)
                <= p.recorded_at
                < payment.recorded_at
            ]
            if len(prior) < BACKDATE_MIN_PRIOR_RECEIPTS:
                insufficient[payment.currency].add("BACKDATED_RECEIPT_LARGE")
                continue
            mid = Decimal(median(prior))
            if Decimal(payment.amount) < BACKDATE_MIN_MULTIPLE * mid:
                continue
            found[payment.currency].append(
                Anomaly(
                    type="BACKDATED_RECEIPT_LARGE",
                    severity="WATCH",
                    currency=payment.currency,
                    subject_type="CUSTOMER",
                    subject_id=payment.customer_id,
                    metric="receipt_amount",
                    observed_value=money(Decimal(payment.amount)),
                    baseline=Baseline("DIRECT_RULE", _q(mid), None, len(prior)),
                    reason_code="RECORDED_AFTER_PAYMENT_DATE",
                    details={
                        "payment_id": str(payment.id),
                        "customer_name": names.get(payment.customer_id)
                        if payment.customer_id
                        else None,
                        "days_recorded_after_payment_date": lag,
                        "recorded_from_device": payment.source_device_id is not None,
                    },
                )
            )

    # ---- overdue threshold newly crossed (D-040; nothing when the threshold is not set)
    if "OVERDUE_THRESHOLD_CROSSED" in wanted:
        for debt in customer_debts(db, tenant_id, now=as_of).debts:
            threshold = debt.overdue_threshold_days
            age = debt.overdue_age_days
            if not debt.is_overdue or threshold is None or age is None:
                continue
            days_past = age - threshold
            if not 1 <= days_past <= OVERDUE_CROSSING_DAYS:
                continue
            found[debt.currency].append(
                Anomaly(
                    type="OVERDUE_THRESHOLD_CROSSED",
                    severity="WATCH",
                    currency=debt.currency,
                    subject_type="CUSTOMER",
                    subject_id=debt.customer_id,
                    metric="outstanding_balance",
                    observed_value=money(debt.balance),
                    baseline=Baseline("DIRECT_RULE"),
                    reason_code="THRESHOLD_CROSSED_RECENTLY",
                    details={
                        "customer_name": debt.customer_name,
                        "overdue_age_days": age,
                        "threshold_days": threshold,
                        "days_past_threshold": days_past,
                    },
                )
            )

    # ---- supplier payable jump: net supplier-ledger change per block vs its own history
    if "SUPPLIER_PAYABLE_JUMP" in wanted:
        supplier_first = {
            currency: overdue_calendar_date(first)
            for currency, first in db.execute(
                select(SupplierLedgerEntry.currency, func.min(SupplierLedgerEntry.effective_at))
                .where(SupplierLedgerEntry.tenant_id == tenant_id)
                .group_by(SupplierLedgerEntry.currency)
            ).all()
            if first is not None
        }
        changes = _Series()
        for currency, effective_at, amount in db.execute(
            select(
                SupplierLedgerEntry.currency,
                SupplierLedgerEntry.effective_at,
                SupplierLedgerEntry.signed_amount,
            ).where(
                SupplierLedgerEntry.tenant_id == tenant_id,
                SupplierLedgerEntry.effective_at >= series_start,
                SupplierLedgerEntry.effective_at <= as_of,
            )
        ).all():
            changes.add(currency, effective_at, Decimal(amount), today)
        for currency in sorted(supplier_first):
            blocks = _covered_blocks(supplier_first[currency], today)
            if len(blocks) < MIN_BASELINE_BLOCKS:
                insufficient[currency].add("SUPPLIER_PAYABLE_JUMP")
                continue
            current, _events, baseline, z = _block_check(
                series=changes, currency=currency, blocks=blocks, use_counts=False
            )
            if current <= 0:
                continue
            report(
                "SUPPLIER_PAYABLE_JUMP",
                currency,
                money(current),
                baseline,
                z,
                "supplier_ledger_net_change_7d",
            )

    # ---- lines sold below their own sale-time cost snapshot (same currency and basis only)
    if "LINE_PRICE_BELOW_SNAPSHOT_COST" in wanted:
        for item, currency, invoice_id, customer_id in db.execute(
            select(InvoiceRevisionItem, InvoiceRevision.currency, Invoice.id, Invoice.customer_id)
            .join(InvoiceRevision, InvoiceRevision.id == InvoiceRevisionItem.invoice_revision_id)
            .join(Invoice, Invoice.current_revision_id == InvoiceRevision.id)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.confirmed_at >= window_start,
                Invoice.confirmed_at <= as_of,
            )
            .order_by(Invoice.id.asc(), InvoiceRevisionItem.line_number.asc())
        ).all():
            if (
                item.unit_cost is None
                or item.cost_currency != currency
                or item.cost_basis is None
                or item.cost_basis != item.price_basis
                or Decimal(item.quantity) <= 0
            ):
                continue  # uncovered lines are never estimated (D-067)
            net_unit = Decimal(item.line_total) / Decimal(item.quantity)
            if net_unit >= Decimal(item.unit_cost):
                continue
            found[currency].append(
                Anomaly(
                    type="LINE_PRICE_BELOW_SNAPSHOT_COST",
                    severity="WATCH",
                    currency=currency,
                    subject_type="INVOICE",
                    subject_id=invoice_id,
                    metric="line_net_unit_price",
                    observed_value=_q(net_unit),
                    baseline=Baseline("DIRECT_RULE", money(Decimal(item.unit_cost)), None, None),
                    reason_code="LINE_BELOW_SNAPSHOT_COST",
                    details={
                        "line_number": item.line_number,
                        "product_name": item.product_name,
                        "unit_cost_snapshot": money(Decimal(item.unit_cost)),
                        "customer_id": str(customer_id) if customer_id else None,
                        "customer_name": names.get(customer_id) if customer_id else None,
                    },
                )
            )

    ordered = {
        currency: sorted(
            rows,
            key=lambda a: (
                _SEVERITY_ORDER[a.severity],
                ANOMALY_TYPES.index(a.type),
                str(a.subject_id),
                str(sorted(a.details.items())),
            ),
        )
        for currency, rows in sorted(found.items())
    }
    return AnomalyReport(
        as_of=as_of,
        window=AnomalyWindow(start=window_start, end=as_of),
        anomalies=ordered,
        insufficient_history={c: sorted(v) for c, v in sorted(insufficient.items())},
    )
