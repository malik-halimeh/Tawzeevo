"""D-089 prioritization and inactivity: bands, components, normalization, per-currency ranking
and deterministic ordering, on hand-built feature rows (no database arithmetic involved)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from tawzeevo_api.services.intelligence.customers import (
    AT_RISK,
    INSUFFICIENT_HISTORY,
    LAPSED,
    NORMAL,
    WATCH,
    classify_inactivity,
    inactivity_status,
    rank_priorities,
    score_features,
)
from tawzeevo_api.services.intelligence.features import CustomerCurrencyFeatures, cadence

AS_OF = datetime(2026, 9, 23, 9, 0, tzinfo=UTC)
ZERO = Decimal("0.0000")


def _features(**overrides: object) -> CustomerCurrencyFeatures:
    base = CustomerCurrencyFeatures(
        customer_id=UUID(int=1),
        customer_name="Maya Market",
        customer_grade="A",
        currency="USD",
        as_of=AS_OF,
        invoice_count_lifetime=0,
        invoice_count_30d=0,
        invoice_count_90d=0,
        sales_30d=ZERO,
        sales_90d=ZERO,
        sales_365d=ZERO,
        average_invoice_value=None,
        first_purchase_at=None,
        last_purchase_at=None,
        days_since_last_purchase=None,
        median_purchase_interval_days=None,
        purchase_interval_mad_days=None,
        history_sufficient=False,
        recency_ratio=None,
        recent_activity_ratio=None,
        balance=ZERO,
        outstanding_balance=ZERO,
        oldest_unpaid_at=None,
        overdue_age_days=None,
        overdue_threshold_days=None,
        is_overdue=False,
        receipts_30d=ZERO,
        receipts_90d=ZERO,
        recent_cancelled_invoices=0,
        recent_receipt_reversals=0,
        recent_negative_adjustments=0,
        recent_cancellation_requests=0,
        recent_refunds=ZERO,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _cadenced(ratio: str, **overrides: object) -> CustomerCurrencyFeatures:
    return _features(
        invoice_count_lifetime=5,
        history_sufficient=True,
        median_purchase_interval_days=Decimal("10"),
        recency_ratio=Decimal(ratio),
        **overrides,
    )


@pytest.mark.parametrize(
    ("ratio", "status"),
    [
        ("1.2499", NORMAL),
        ("1.25", WATCH),
        ("1.7499", WATCH),
        ("1.75", AT_RISK),
        ("2.4999", AT_RISK),
        ("2.50", LAPSED),
    ],
)
def test_inactivity_band_boundaries(ratio, status):
    assert inactivity_status(_cadenced(ratio)) == status


def test_cadence_needs_three_invoices_and_a_positive_median():
    day = timedelta(days=1)
    two = [AS_OF - 20 * day, AS_OF - 10 * day]
    assert cadence(two, AS_OF) == (None, None, False, None)
    same_day = [AS_OF - 5 * day, AS_OF - 5 * day, AS_OF - 5 * day]
    median, _mad, eligible, ratio = cadence(same_day, AS_OF)
    assert median == 0 and eligible is False and ratio is None  # no division by zero
    regular = [AS_OF - 50 * day, AS_OF - 40 * day, AS_OF - 30 * day]
    median, mad, eligible, ratio = cadence(regular, AS_OF)
    assert (median, mad, eligible, ratio) == (Decimal(10), Decimal(0), True, Decimal("3.0000"))


def test_missing_history_is_not_bad_behaviour_and_components_normalize():
    newcomer = score_features(_features(invoice_count_lifetime=1))
    assert newcomer.components["relationship_inactivity"] is None
    assert newcomer.components["activity_decline"] is None
    assert newcomer.score == 0 and newcomer.band == "LOW"
    assert [r.code for r in newcomer.reasons] == ["INSUFFICIENT_PURCHASE_HISTORY"]
    # The same overdue debt: normalized over the 50 available points vs the full 100.
    debt = {
        "balance": Decimal("80"),
        "outstanding_balance": Decimal("80"),
        "is_overdue": True,
        "overdue_age_days": 10,
        "overdue_threshold_days": 7,
    }
    short = score_features(_features(invoice_count_lifetime=1, **debt))
    assert short.components["collection_urgency"] == 30 and short.score == 60
    full = score_features(_cadenced("1.0", recent_activity_ratio=Decimal("1.0"), **debt))
    assert full.components["collection_urgency"] == 30 and full.score == 30
    assert full.suggested_action_code == "COLLECT_OVERDUE"


def test_collection_urgency_levels_and_reasons():
    outstanding = score_features(
        _features(balance=Decimal("5"), outstanding_balance=Decimal("5"), overdue_age_days=3)
    )
    assert outstanding.components["collection_urgency"] == 10
    assert outstanding.reasons[0].code == "OUTSTANDING_BALANCE"
    assert outstanding.suggested_action_code == "FOLLOW_UP_BALANCE"
    old = score_features(
        _features(
            balance=Decimal("5"),
            outstanding_balance=Decimal("5"),
            is_overdue=True,
            overdue_age_days=14,
            overdue_threshold_days=7,
        )
    )
    assert old.components["collection_urgency"] == 40
    assert old.reasons[0].code == "OLD_OVERDUE_BALANCE"
    assert old.reasons[0].context == {"overdue_age_days": 14, "threshold_days": 7}
    credit = score_features(_features(balance=Decimal("-5")))
    assert credit.components["collection_urgency"] == 0 and credit.reasons == []


def test_inactivity_without_debt_still_creates_attention():
    lapsed = score_features(_cadenced("3.0"))
    assert lapsed.components["relationship_inactivity"] == 30
    assert lapsed.suggested_action_code == "REACTIVATE_CUSTOMER"
    assert lapsed.reasons[0].code == "PAST_NORMAL_PURCHASE_INTERVAL"
    assert lapsed.score == round(30 * 100 / 80)  # decline unavailable: 80 available points


def test_activity_decline_and_friction_reasons():
    decline = score_features(_cadenced("1.0", recent_activity_ratio=Decimal("0.4")))
    assert decline.components["activity_decline"] == 20
    assert decline.suggested_action_code == "CHECK_ACTIVITY_DECLINE"
    assert any(r.code == "ACTIVITY_DOWN_VS_90D" for r in decline.reasons)
    mild = score_features(_cadenced("1.0", recent_activity_ratio=Decimal("0.6")))
    assert mild.components["activity_decline"] == 10
    steady = score_features(_cadenced("1.0", recent_activity_ratio=Decimal("0.75")))
    assert steady.components["activity_decline"] == 0
    friction = score_features(_features(recent_cancelled_invoices=1, recent_receipt_reversals=2))
    assert friction.components["friction_signals"] == 10  # capped
    assert {r.code for r in friction.reasons} == {"RECENT_CANCELLATIONS", "RECENT_REVERSALS"}
    assert friction.suggested_action_code == "REVIEW_RECENT_FRICTION"


def test_score_band_boundaries():
    # 25/50 exactly: friction 5 of 10 + collection 0 of 40 -> 10%; build exact bands instead.
    medium = score_features(
        _features(
            invoice_count_lifetime=1,
            recent_cancelled_invoices=1,
            balance=Decimal("1"),
            outstanding_balance=Decimal("1"),
            overdue_age_days=0,
        )
    )
    # collection 10 + friction 5 = 15 of 50 -> 30
    assert medium.score == 30 and medium.band == "MEDIUM"
    high = score_features(
        _features(
            recent_cancelled_invoices=1,
            balance=Decimal("1"),
            outstanding_balance=Decimal("1"),
            is_overdue=True,
            overdue_age_days=8,
            overdue_threshold_days=7,
        )
    )
    # 30 + 5 = 35 of 50 -> 70
    assert high.score == 70 and high.band == "HIGH"
    exact_high = score_features(
        _features(
            balance=Decimal("1"),
            outstanding_balance=Decimal("1"),
            is_overdue=True,
            overdue_age_days=8,
            overdue_threshold_days=7,
        )
    )
    assert exact_high.score == 60 and exact_high.band == "HIGH"
    low = score_features(
        _cadenced("1.0", recent_activity_ratio=Decimal("1"), recent_cancelled_invoices=1)
    )
    assert low.score == 5 and low.band == "LOW"


def test_grade_is_a_tie_break_not_points_and_currencies_rank_apart():
    same = {"recent_cancelled_invoices": 1}
    a = _features(customer_id=uuid4(), customer_name="Zed", customer_grade="A+", **same)
    b = _features(customer_id=uuid4(), customer_name="Abe", customer_grade="B", **same)
    lbp = _features(
        customer_id=a.customer_id,
        customer_name="Zed",
        currency="LBP",
        customer_grade="A+",
        recent_receipt_reversals=2,
    )
    assert score_features(a).score == score_features(b).score
    ranked = rank_priorities([b, lbp, a])
    assert list(ranked) == ["LBP", "USD"]
    assert [p.features.customer_name for p in ranked["USD"]] == ["Zed", "Abe"]
    assert [p.features.currency for p in ranked["LBP"]] == ["LBP"]
    # Deterministic: input order never changes the output.
    assert rank_priorities([a, b, lbp]) == ranked


def test_inactivity_list_orders_by_severity_and_skips_balance_only_pairs():
    rows = [
        _features(customer_id=uuid4(), customer_name="New", invoice_count_lifetime=2),
        _cadenced("1.0", customer_id=uuid4(), customer_name="Steady"),
        _cadenced(
            "3.0",
            customer_id=uuid4(),
            customer_name="Gone",
            outstanding_balance=Decimal("4"),
            balance=Decimal("4"),
        ),
        _cadenced("1.8", customer_id=uuid4(), customer_name="Slow"),
        _features(
            customer_id=uuid4(),
            customer_name="Opening only",
            balance=Decimal("9"),
            outstanding_balance=Decimal("9"),
        ),
        _features(
            customer_id=uuid4(),
            customer_name="Same day",
            invoice_count_lifetime=3,
            median_purchase_interval_days=Decimal(0),
        ),
    ]
    usd = classify_inactivity(rows)["USD"]
    assert [(r.features.customer_name, r.status) for r in usd] == [
        ("Gone", LAPSED),
        ("Slow", AT_RISK),
        ("Steady", NORMAL),
        ("New", INSUFFICIENT_HISTORY),
        ("Same day", INSUFFICIENT_HISTORY),
    ]
    assert usd[0].reason_codes == ["PAST_NORMAL_PURCHASE_INTERVAL", "OUTSTANDING_BALANCE"]
    assert usd[3].reason_codes == ["INSUFFICIENT_PURCHASE_HISTORY"]
    assert usd[4].reason_codes == ["ZERO_MEDIAN_INTERVAL"]
