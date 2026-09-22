"""Daily customer prioritization and customer inactivity risk (D-089).

Both are deterministic workflow heuristics over the shared feature layer, never probabilities
and never financial values. Every score is explained by its returned components and reason codes;
ranking happens only inside one currency. Customer grade is context and a tie-break, never points.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from tawzeevo_api.services.intelligence.features import (
    CustomerCurrencyFeatures,
    customer_features,
)

# ---- inactivity bands on recency_ratio = days since last purchase / median interval
WATCH_RATIO = Decimal("1.25")
AT_RISK_RATIO = Decimal("1.75")
LAPSED_RATIO = Decimal("2.50")

NORMAL = "NORMAL"
WATCH = "WATCH"
AT_RISK = "AT_RISK"
LAPSED = "LAPSED"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
_STATUS_ORDER = {LAPSED: 0, AT_RISK: 1, WATCH: 2, NORMAL: 3, INSUFFICIENT_HISTORY: 4}

# ---- prioritization component maxima and rules
COLLECTION_MAX = 40
INACTIVITY_MAX = 30
DECLINE_MAX = 20
FRICTION_MAX = 10

COLLECTION_OLD_OVERDUE = 40  # overdue age >= 2 x threshold
COLLECTION_OVERDUE = 30
COLLECTION_OUTSTANDING = 10  # a balance that is not (or cannot be) overdue
OLD_OVERDUE_MULTIPLIER = 2

INACTIVITY_POINTS = {NORMAL: 0, WATCH: 10, AT_RISK: 20, LAPSED: 30}

DECLINE_WATCH_RATIO = Decimal("0.75")  # 30d activity below 75% of the 90d average block
DECLINE_STRONG_RATIO = Decimal("0.50")
DECLINE_WATCH_POINTS = 10
DECLINE_STRONG_POINTS = 20

FRICTION_POINTS_PER_EVENT = 5

HIGH_BAND = 50
MEDIUM_BAND = 25

_GRADE_ORDER = {"A+": 0, "A": 1, "B+": 2, "B": 3, None: 4}


def inactivity_status(features: CustomerCurrencyFeatures) -> str:
    ratio = features.recency_ratio
    if not features.history_sufficient or ratio is None:
        return INSUFFICIENT_HISTORY
    if ratio >= LAPSED_RATIO:
        return LAPSED
    if ratio >= AT_RISK_RATIO:
        return AT_RISK
    if ratio >= WATCH_RATIO:
        return WATCH
    return NORMAL


@dataclass(frozen=True)
class Reason:
    code: str
    value: Decimal | int | str | None = None
    context: Mapping[str, Decimal | int | str | None] | None = None


@dataclass(frozen=True)
class Priority:
    features: CustomerCurrencyFeatures
    score: int
    band: str
    components: dict[str, int | None]  # None = not available (excluded from the denominator)
    reasons: list[Reason]
    suggested_action_code: str
    inactivity_status: str


@dataclass(frozen=True)
class Inactivity:
    features: CustomerCurrencyFeatures
    status: str
    reason_codes: list[str]


def _collection(f: CustomerCurrencyFeatures, reasons: list[Reason]) -> int:
    if f.outstanding_balance <= 0:
        return 0
    threshold = f.overdue_threshold_days
    age = f.overdue_age_days
    if f.is_overdue and threshold is not None and age is not None:
        context = {"overdue_age_days": age, "threshold_days": threshold}
        if age >= OLD_OVERDUE_MULTIPLIER * max(threshold, 1):
            reasons.append(Reason("OLD_OVERDUE_BALANCE", f.outstanding_balance, context))
            return COLLECTION_OLD_OVERDUE
        reasons.append(Reason("OVERDUE_BALANCE", f.outstanding_balance, context))
        return COLLECTION_OVERDUE
    reasons.append(
        Reason("OUTSTANDING_BALANCE", f.outstanding_balance, {"oldest_unpaid_age_days": age})
    )
    return COLLECTION_OUTSTANDING


def _inactivity(f: CustomerCurrencyFeatures, status: str, reasons: list[Reason]) -> int | None:
    if status == INSUFFICIENT_HISTORY:
        if f.invoice_count_lifetime > 0:
            reasons.append(Reason("INSUFFICIENT_PURCHASE_HISTORY", f.invoice_count_lifetime))
        return None
    points = INACTIVITY_POINTS[status]
    if points:
        reasons.append(
            Reason(
                "PAST_NORMAL_PURCHASE_INTERVAL",
                f.recency_ratio,
                {
                    "days_since_last_purchase": f.days_since_last_purchase,
                    "median_purchase_interval_days": f.median_purchase_interval_days,
                    "status": status,
                },
            )
        )
    return points


def _decline(f: CustomerCurrencyFeatures, reasons: list[Reason]) -> int | None:
    ratio = f.recent_activity_ratio
    if ratio is None:
        return None
    if ratio >= DECLINE_WATCH_RATIO:
        return 0
    points = DECLINE_STRONG_POINTS if ratio < DECLINE_STRONG_RATIO else DECLINE_WATCH_POINTS
    reasons.append(
        Reason("ACTIVITY_DOWN_VS_90D", ratio, {"sales_30d": f.sales_30d, "sales_90d": f.sales_90d})
    )
    return points


def _friction(f: CustomerCurrencyFeatures, reasons: list[Reason]) -> int:
    cancellations = f.recent_cancelled_invoices + f.recent_cancellation_requests
    reversals = f.recent_receipt_reversals + f.recent_negative_adjustments
    if cancellations:
        reasons.append(Reason("RECENT_CANCELLATIONS", cancellations))
    if reversals:
        reasons.append(Reason("RECENT_REVERSALS", reversals))
    return min(FRICTION_MAX, FRICTION_POINTS_PER_EVENT * (cancellations + reversals))


def _action(components: dict[str, int | None], reasons: list[Reason], status: str) -> str:
    codes = {reason.code for reason in reasons}
    if codes & {"OVERDUE_BALANCE", "OLD_OVERDUE_BALANCE"}:
        return "COLLECT_OVERDUE"
    if status in (AT_RISK, LAPSED):
        return "REACTIVATE_CUSTOMER"
    if "OUTSTANDING_BALANCE" in codes:
        return "FOLLOW_UP_BALANCE"
    if (components.get("activity_decline") or 0) > 0:
        return "CHECK_ACTIVITY_DECLINE"
    if (components.get("friction_signals") or 0) > 0:
        return "REVIEW_RECENT_FRICTION"
    return "ROUTINE_CHECK_IN"


def score_features(f: CustomerCurrencyFeatures) -> Priority:
    """Transparent component score, normalized over the components whose inputs exist."""
    reasons: list[Reason] = []
    status = inactivity_status(f)
    components: dict[str, int | None] = {
        "collection_urgency": _collection(f, reasons),
        "relationship_inactivity": _inactivity(f, status, reasons),
        "activity_decline": _decline(f, reasons),
        "friction_signals": _friction(f, reasons),
    }
    maxima = {
        "collection_urgency": COLLECTION_MAX,
        "relationship_inactivity": INACTIVITY_MAX,
        "activity_decline": DECLINE_MAX,
        "friction_signals": FRICTION_MAX,
    }
    available = sum(maxima[name] for name, value in components.items() if value is not None)
    earned = sum(value for value in components.values() if value is not None)
    score = (
        int(
            (Decimal(earned) * 100 / Decimal(available)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        if available
        else 0
    )
    band = "HIGH" if score >= HIGH_BAND else "MEDIUM" if score >= MEDIUM_BAND else "LOW"
    return Priority(
        features=f,
        score=score,
        band=band,
        components=components,
        reasons=reasons,
        suggested_action_code=_action(components, reasons, status),
        inactivity_status=status,
    )


def _rank_key(p: Priority) -> tuple[object, ...]:
    f = p.features
    return (
        -p.score,
        _GRADE_ORDER.get(f.customer_grade, 4),
        f.customer_name.casefold(),
        str(f.customer_id),
    )


def rank_priorities(features: list[CustomerCurrencyFeatures]) -> dict[str, list[Priority]]:
    """Per-currency ranking of every pair with a non-zero score; never one mixed list."""
    groups: dict[str, list[Priority]] = defaultdict(list)
    for f in features:
        priority = score_features(f)
        if priority.score > 0:
            groups[f.currency].append(priority)
    return {currency: sorted(rows, key=_rank_key) for currency, rows in sorted(groups.items())}


def classify_inactivity(features: list[CustomerCurrencyFeatures]) -> dict[str, list[Inactivity]]:
    groups: dict[str, list[Inactivity]] = defaultdict(list)
    for f in features:
        if f.invoice_count_lifetime == 0:
            continue  # a balance without purchases has no cadence to judge
        status = inactivity_status(f)
        codes: list[str] = []
        if status == INSUFFICIENT_HISTORY:
            codes.append(
                "ZERO_MEDIAN_INTERVAL"
                if f.median_purchase_interval_days is not None
                else "INSUFFICIENT_PURCHASE_HISTORY"
            )
        elif status != NORMAL:
            codes.append("PAST_NORMAL_PURCHASE_INTERVAL")
        if f.recent_activity_ratio is not None and f.recent_activity_ratio < DECLINE_WATCH_RATIO:
            codes.append("ACTIVITY_DOWN_VS_90D")
        if f.outstanding_balance > 0:
            codes.append("OVERDUE_BALANCE" if f.is_overdue else "OUTSTANDING_BALANCE")
        if f.recent_cancelled_invoices or f.recent_cancellation_requests:
            codes.append("RECENT_CANCELLATIONS")
        groups[f.currency].append(Inactivity(features=f, status=status, reason_codes=codes))
    for rows in groups.values():
        rows.sort(
            key=lambda r: (
                _STATUS_ORDER[r.status],
                -(r.features.recency_ratio or Decimal(0)),
                r.features.customer_name.casefold(),
                str(r.features.customer_id),
            )
        )
    return dict(sorted(groups.items()))


def daily_priorities(
    db: Session, tenant_id: UUID, *, as_of: datetime | None = None
) -> tuple[datetime, dict[str, list[Priority]]]:
    as_of = as_of or datetime.now(UTC)
    return as_of, rank_priorities(customer_features(db, tenant_id, as_of=as_of))


def inactivity_risk(
    db: Session, tenant_id: UUID, *, as_of: datetime | None = None
) -> tuple[datetime, dict[str, list[Inactivity]]]:
    as_of = as_of or datetime.now(UTC)
    return as_of, classify_inactivity(customer_features(db, tenant_id, as_of=as_of))
