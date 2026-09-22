"""D-089 anomaly detection: robust-baseline boundaries, minimum history, per-currency evidence,
same-customer comparison, backdated receipts, overdue crossing (threshold NULL and set), supplier
payable jump, below-cost lines, determinism and no writes."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from test_delivery_tasks import _post
from test_intelligence_features import canonical_counts, set_confirmed_at
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_procurement import _confirm_invoice

from tawzeevo_api.services.intelligence.anomalies import (
    _covered_blocks,
    _severity,
    detect_anomalies,
    robust_z,
)

WEEKLY_DAYS = (10, 17, 24, 31, 38, 45, 52, 59)  # one purchase in each of baseline blocks 1..8


def _types(report, currency="USD"):
    return [a.type for a in report.anomalies.get(currency, [])]


def test_robust_z_scale_floors_and_severity_boundaries():
    mid, mad, z = robust_z(Decimal("13"), [Decimal("10")] * 6)
    assert (mid, mad, z) == (Decimal("10"), Decimal("0"), Decimal("3"))  # floor = 10% of median
    assert _severity(Decimal("2.9999")) is None
    assert _severity(Decimal("3")) == "WATCH" and _severity(Decimal("-3")) == "WATCH"
    assert _severity(Decimal("5")) == "HIGH"
    _mid, _mad, z = robust_z(Decimal("3"), [Decimal("0")] * 6, count_series=True)
    assert z == Decimal("3")  # three events against a quiet history: one event is the unit
    _mid, _mad, z = robust_z(Decimal("5"), [Decimal("0")] * 6)
    assert z is None  # an all-zero money baseline has no scale


def test_zero_heavy_money_series_scale_by_the_largest_past_value():
    """median == MAD == 0: a repeat of past activity is ordinary; only a multiple of the largest
    past block is unusual (WATCH >= 3x, HIGH >= 5x). Deterministic, never a division by zero."""
    monthly = [Decimal("0")] * 3 + [Decimal("200")] + [Decimal("0")] * 3 + [Decimal("200")]
    assert robust_z(Decimal("200"), monthly)[2] == Decimal("1")  # the usual monthly purchase
    sporadic = [Decimal("0")] * 6 + [Decimal("100")]
    assert _severity(robust_z(Decimal("299.99"), sporadic)[2]) is None
    assert _severity(robust_z(Decimal("300"), sporadic)[2]) == "WATCH"
    assert _severity(robust_z(Decimal("499.99"), sporadic)[2]) == "WATCH"
    assert _severity(robust_z(Decimal("500"), sporadic)[2]) == "HIGH"
    # Negative blocks (supplier payments) count by magnitude; an all-zero baseline has no scale.
    assert robust_z(Decimal("150"), [Decimal("0")] * 6 + [Decimal("-50")])[2] == Decimal("3")
    assert robust_z(Decimal("1000"), [Decimal("0")] * 7)[2] is None
    # Once most blocks are non-zero the ordinary MAD path applies again.
    busy = [Decimal(v) for v in ("0", "0", "0", "90", "100", "110", "100")]
    mid, mad, z = robust_z(Decimal("100"), busy)
    assert (mid, mad) == (Decimal("90"), Decimal("20")) and _severity(z) is None


def test_minimum_history_counts_only_whole_blocks_after_first_activity():
    today = date(2026, 9, 23)
    assert _covered_blocks(None, today) == []
    assert _covered_blocks(today - timedelta(days=47), today) == [1, 2, 3, 4, 5]
    assert _covered_blocks(today - timedelta(days=48), today) == [1, 2, 3, 4, 5, 6]


def _weekly_customer(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])  # cost 8.0000 / piece
    now = datetime.now(UTC)
    for days in WEEKLY_DAYS:
        invoice = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
        set_confirmed_at(session_factory, invoice["id"], now - timedelta(days=days))
    return tenant, token, product, customer


def test_unusual_week_is_detected_with_its_evidence(client, session_factory):
    tenant, token, product, customer = _weekly_customer(client, session_factory, "anomhigh")
    big = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "10")
    # A line sold below its sale-time cost snapshot: 2 x 12.5 - 10 discount = 7.625 < 8 per piece.
    payload = _confirmable_payload(customer["id"], product["id"])
    payload["items"][0]["line_discount_expression"] = "10"  # type: ignore[index]
    cheap_draft = _post(client, tenant, token, "/api/v1/invoices", payload).json()
    cheap = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{cheap_draft['id']}/confirm",
        {"expected_revision_id": cheap_draft["current_revision_id"]},
    ).json()
    for _ in range(3):
        doomed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
        assert (
            _post(
                client,
                tenant,
                token,
                f"/api/v1/invoices/{doomed['id']}/cancel",
                {"idempotency_key": str(uuid4()), "reason": "x"},
            ).status_code
            == 200
        )
    as_of = datetime.now(UTC) + timedelta(seconds=5)
    before = canonical_counts(session_factory)
    with session_factory() as db:
        report = detect_anomalies(db, UUID(tenant), as_of=as_of)
        assert detect_anomalies(db, UUID(tenant), as_of=as_of) == report  # stable set and order
    assert canonical_counts(session_factory) == before

    by_type = {a.type: a for a in report.anomalies["USD"]}
    sales = by_type["SALES_PERIOD_HIGH"]
    assert sales.severity == "HIGH" and sales.reason_code == "ABOVE_BASELINE"
    assert sales.observed_value == Decimal(big["net_sales"]) + Decimal(cheap["net_sales"])
    assert sales.baseline.method == "MEDIAN_MAD" and sales.baseline.sample_size == 7
    assert sales.details["invoice_count"] == 2

    value = by_type["CUSTOMER_INVOICE_VALUE_HIGH"]
    assert value.subject_type == "INVOICE" and str(value.subject_id) == big["id"]
    assert value.details["customer_name"] == customer["name"]
    assert value.baseline.sample_size == len(WEEKLY_DAYS)

    below = by_type["LINE_PRICE_BELOW_SNAPSHOT_COST"]
    assert str(below.subject_id) == cheap["id"]
    assert below.observed_value == Decimal("7.6250")
    assert below.details["unit_cost_snapshot"] == Decimal("8.0000")

    spike = by_type["CANCELLATION_SPIKE"]
    assert spike.observed_value == Decimal("3") and spike.severity == "WATCH"
    assert report.insufficient_history == {}
    # No accusation language anywhere in the machine-readable output.
    text = repr(report).lower()
    assert "fraud" not in text and "suspicious" not in text


def test_quiet_week_is_low_and_thin_history_is_not_an_anomaly(client, session_factory):
    tenant, _token, _product, _customer = _weekly_customer(client, session_factory, "anomlow")
    with session_factory() as db:
        report = detect_anomalies(db, UUID(tenant))
    assert _types(report) == ["SALES_PERIOD_LOW"]
    assert report.anomalies["USD"][0].reason_code == "BELOW_BASELINE"

    owner, fresh, token = _owner_context(client, session_factory, "anomfresh")
    _category, product, customer = _catalog(client, fresh, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, fresh, product["id"])
    _confirm_invoice(client, fresh, token, customer["id"], product["id"], "50")
    with session_factory() as db:
        thin = detect_anomalies(db, UUID(fresh))
    assert thin.anomalies == {}
    assert thin.insufficient_history == {
        "USD": ["CANCELLATION_SPIKE", "REFUND_SPIKE", "REVERSAL_SPIKE", "SALES_PERIOD"]
    }


def test_overdue_crossing_needs_a_threshold_and_a_recent_crossing(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "anomdue")
    _category, _product, recent = _catalog(client, tenant, token, name="Cedar Water")
    old = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": "Old Debtor", "phone": "+96171000888"},
    ).json()
    now = datetime.now(UTC)
    for customer, days in ((recent, 10), (old, 40)):
        assert (
            _post(
                client,
                tenant,
                token,
                "/api/v1/customer-ledger/opening-balances",
                {
                    "idempotency_key": str(uuid4()),
                    "customer_id": customer["id"],
                    "currency": "USD",
                    "signed_amount": "50.0000",
                    "effective_at": (now - timedelta(days=days)).isoformat(),
                },
            ).status_code
            == 201
        )
    with session_factory() as db:
        assert (
            detect_anomalies(db, UUID(tenant), types=["OVERDUE_THRESHOLD_CROSSED"]).anomalies == {}
        )
    client.put(
        f"/api/v1/customer-ledger/settings?tenant_id={tenant}",
        headers=_auth(token),
        json={"customer_overdue_threshold_days": 7},
    )
    with session_factory() as db:
        report = detect_anomalies(db, UUID(tenant), types=["OVERDUE_THRESHOLD_CROSSED"])
    (crossed,) = report.anomalies["USD"]
    assert str(crossed.subject_id) == recent["id"]  # the 40-day debt is old news, not "new"
    assert crossed.details["days_past_threshold"] == 3
    assert crossed.observed_value == Decimal("50.0000")


def test_large_backdated_receipt_uses_recorded_at_against_paid_at(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "anomback")
    _category, _product, customer = _catalog(client, tenant, token, name="Cedar Water")
    now = datetime.now(UTC)

    def receipt(amount: str, paid_days_ago: int) -> dict[str, object]:
        response = _post(
            client,
            tenant,
            token,
            "/api/v1/payments/customer-receipts",
            {
                "idempotency_key": str(uuid4()),
                "customer_id": customer["id"],
                "amount": amount,
                "currency": "USD",
                "paid_at": (now - timedelta(days=paid_days_ago)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    for _ in range(5):
        receipt("10", 0)
    receipt("10", 12)  # backdated but ordinary in size: not flagged
    large = receipt("50", 12)
    with session_factory() as db:
        report = detect_anomalies(db, UUID(tenant), types=["BACKDATED_RECEIPT_LARGE"])
    (flag,) = report.anomalies["USD"]
    assert flag.details["payment_id"] == large["id"]
    assert flag.details["days_recorded_after_payment_date"] == 12
    assert flag.baseline.median == Decimal("10.0000") and flag.baseline.method == "DIRECT_RULE"


def test_supplier_payable_jump_against_sporadic_history(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "anomsupp")
    _category, product, _customer = _catalog(client, tenant, token, name="Cedar Water")
    supplier = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Mill"}).json()
    assert (
        client.post(
            f"/api/v1/supplier-ledger/opening-balances?tenant_id={tenant}",
            headers=_auth(token),
            json={
                "idempotency_key": str(uuid4()),
                "supplier_id": supplier["id"],
                "currency": "USD",
                "signed_amount": "10.0000",
                "effective_at": (datetime.now(UTC) - timedelta(days=48)).isoformat(),
            },
        ).status_code
        == 201
    )
    with session_factory() as db:
        assert detect_anomalies(db, UUID(tenant), types=["SUPPLIER_PAYABLE_JUMP"]).anomalies == {}
    bought = _post(
        client,
        tenant,
        token,
        "/api/v1/supplier-purchases",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier["id"],
            "currency": "USD",
            "items": [{"product_id": product["id"], "quantity": "20", "unit_cost": "10.0000"}],
        },
    )
    assert bought.status_code == 201, bought.text
    with session_factory() as db:
        report = detect_anomalies(db, UUID(tenant), types=["SUPPLIER_PAYABLE_JUMP"])
    (jump,) = report.anomalies["USD"]
    assert jump.observed_value == Decimal("200.0000") and jump.severity == "HIGH"
    assert jump.subject_type == "TENANT"
