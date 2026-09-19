"""Phase 8 P8-M1: trusted metrics reconcile to the canonical rows (PHASE_08.md A/B/C/J;
D-064–D-068) — seeded reconciliation, cancellation, opening balance, receipts, currencies,
event flow, profit coverage, tenant-calendar boundaries, owner-only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from test_delivery_tasks import _driver, _get, _post
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _login,
    _owner_context,
    _user,
)
from test_procurement import _confirm_invoice

from tawzeevo_api.models import Invoice, InvoiceRevisionItem, SystemUserType
from tawzeevo_api.services.analytics import resolve_period

BEIRUT = ZoneInfo("Asia/Beirut")


def _amount(rows, currency):
    return next((r["amount"] for r in rows if r["currency"] == currency), None)


def test_period_boundaries_follow_the_tenant_calendar():
    # 2026-03-29 is the DST switch in Lebanon; 30 days back from a March-29 evening must start at
    # local midnight of Feb 28 whatever the UTC offset that day had.
    now = datetime(2026, 3, 29, 20, 0, tzinfo=BEIRUT).astimezone(UTC)
    period = resolve_period("30d", now)
    assert period.start is not None
    assert period.start.astimezone(BEIRUT) == datetime(2026, 2, 28, 0, 0, tzinfo=BEIRUT)
    assert resolve_period("all", now).start is None


def test_overview_reconciles_seed_by_currency_and_excludes_cancelled_and_openings(
    client, session_factory
):
    owner, tenant, token = _owner_context(client, session_factory, "p8seed")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])  # cost 8.0000 / piece
    _c2, product_lbp, customer_lbp = _catalog(
        client, tenant, token, name="Bread", barcode="5280000000043", currency="LBP", price="90000"
    )
    lbp_supplier = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Mill"}).json()
    lbp_cost = _post(
        client,
        tenant,
        token,
        f"/api/v1/suppliers/products/{product_lbp['id']}/costs",
        {
            "supplier_id": lbp_supplier["id"],
            "unit_cost": "60000",
            "currency": "LBP",
            "cost_basis": "PIECE",
        },
    )
    assert lbp_cost.status_code == 201, lbp_cost.text

    # Opening balance (never sales), two USD invoices (one later cancelled), one LBP invoice.
    opening = _post(
        client,
        tenant,
        token,
        "/api/v1/customer-ledger/opening-balances",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "currency": "USD",
            "signed_amount": "100.0000",
            "effective_at": datetime.now(UTC).isoformat(),
        },
    )
    assert opening.status_code == 201, opening.text
    kept = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    doomed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "5")
    lbp_payload = _confirmable_payload(customer_lbp["id"], product_lbp["id"])
    lbp_payload["currency"] = "LBP"
    lbp_payload["items"][0]["barcode"] = "5280000000043"  # type: ignore[index]
    lbp_payload["items"][0]["quantity_expression"] = "1"  # type: ignore[index]
    lbp_draft = _post(client, tenant, token, "/api/v1/invoices", lbp_payload)
    assert lbp_draft.status_code == 201, lbp_draft.text
    lbp_confirmed = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{lbp_draft.json()['id']}/confirm",
        {"expected_revision_id": lbp_draft.json()["current_revision_id"]},
    )
    assert lbp_confirmed.status_code == 200, lbp_confirmed.text
    lbp = lbp_confirmed.json()
    cancelled = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{doomed['id']}/cancel",
        {"idempotency_key": str(uuid4()), "reason": "mistake"},
    )
    assert cancelled.status_code == 200, cancelled.text
    # A receipt of 10 and a reversed receipt of 5 (nets to 10).
    receipt = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/customer-receipts",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert receipt.status_code == 201, receipt.text
    second = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/customer-receipts",
        {
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "5",
            "currency": "USD",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    ).json()
    reversed_ = _post(
        client,
        tenant,
        token,
        f"/api/v1/payments/{second['id']}/reverse",
        {"idempotency_key": str(uuid4()), "reason": "bounced"},
    )
    assert reversed_.status_code == 201, reversed_.text
    # Refunds are credit-limited (Phase 3); with no credit here they are simply absent.

    overview = _get(client, tenant, token, "/api/v1/analytics/overview")
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["period"]["key"] == "30d" and body["period"]["timezone"] == "Asia/Beirut"
    assert body["confirmed_invoices"] == 2  # the cancelled one is out
    assert _amount(body["invoiced_sales"], "USD") == kept["net_sales"]  # opening balance excluded
    assert _amount(body["invoiced_sales"], "LBP") == lbp["net_sales"]
    assert len(body["invoiced_sales"]) == 2  # never combined into one scalar
    assert _amount(body["customer_receipts"], "USD") == "10.0000"
    assert body["customer_refunds"] == []
    # Outstanding = opening 100 + kept invoice − receipts 10 (cancelled invoice reversed).
    expected_outstanding = Decimal("100") + Decimal(kept["net_sales"]) - Decimal("10")
    assert Decimal(_amount(body["customer_outstanding"], "USD")) == expected_outstanding
    assert _amount(body["customer_outstanding"], "LBP") == lbp["net_sales"]
    profit = {row["currency"]: row for row in body["gross_profit"]}
    assert profit["USD"]["coverage_percent"] == "100.0000" and profit["USD"]["uncovered_lines"] == 0
    # (12.5 − 8) × 2 minus the line-level discount/markup effects are inside effective price;
    # the exact figure is the sale-time snapshot arithmetic, recomputed independently here.
    with session_factory() as db:
        invoice = db.get(Invoice, UUID(kept["id"]))
        assert invoice is not None
        lines = (
            db.query(InvoiceRevisionItem)
            .filter_by(invoice_revision_id=invoice.current_revision_id)
            .all()
        )
        expected = sum(
            (Decimal(line.effective_unit_price) - Decimal(line.unit_cost)) * Decimal(line.quantity)
            for line in lines
        )
    assert Decimal(profit["USD"]["gross_profit"]) == expected.quantize(Decimal("0.0001"))

    # The cancelled invoice keeps its history but never counts; "all" and "1y" agree with 30d today.
    for key in ("all", "1y", "90d"):
        same = client.get(
            f"/api/v1/analytics/overview?tenant_id={tenant}&period={key}", headers=_auth(token)
        ).json()
        assert same["invoiced_sales"] == body["invoiced_sales"], key
    bad = client.get(
        f"/api/v1/analytics/overview?tenant_id={tenant}&period=7d", headers=_auth(token)
    )
    assert bad.status_code == 422

    # Per-invoice view: receipts applied and outstanding for the kept invoice.
    single = _get(client, tenant, token, f"/api/v1/analytics/invoices/{kept['id']}").json()
    assert single["net_sales"] == kept["net_sales"] and single["status"] == "CONFIRMED"
    assert Decimal(single["receipts_applied"]) + Decimal(single["outstanding"]) == Decimal(
        kept["net_sales"]
    )
    assert single["gross_profit"]["coverage_percent"] == "100.0000"

    # Owner-only: a driver and another business get nothing.
    _d, driver_token, _m = _driver(client, session_factory, tenant, "driver-p8@example.com")
    assert _get(client, tenant, driver_token, "/api/v1/analytics/overview").status_code == 403
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p8seed2")
    other = _get(client, other_tenant, other_token, "/api/v1/analytics/overview").json()
    assert other["invoiced_sales"] == [] and other["confirmed_invoices"] == 0
    admin = _user(session_factory, "admin-p8-x@example.com", SystemUserType.ADMIN)
    assert (
        _get(client, tenant, _login(client, admin.email), "/api/v1/analytics/overview").status_code
        == 403
    )


def test_event_flow_dates_confirmation_edit_delta_and_cancellation(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p8flow")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    initial = _post(
        client,
        tenant,
        token,
        "/api/v1/invoices",
        _confirmable_payload(customer["id"], product["id"]),
    ).json()
    confirmed = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{initial['id']}/confirm",
        {"expected_revision_id": initial["current_revision_id"]},
    ).json()
    net_before = Decimal(confirmed["net_sales"])
    # Post-confirmation edit: quantity 2 → 1 posts a negative delta on acceptance.
    payload = _confirmable_payload(
        customer["id"], product["id"], predecessor_id=confirmed["current_revision_id"]
    )
    payload["items"][0]["quantity_expression"] = "1"  # type: ignore[index]
    revised = client.put(
        f"/api/v1/invoices/{initial['id']}",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json=payload,
    )
    assert revised.status_code == 200, revised.text
    net_after = Decimal(revised.json()["net_sales"])
    other = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "3")
    _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{other['id']}/cancel",
        {"idempotency_key": str(uuid4()), "reason": "x"},
    )

    flow = _get(client, tenant, token, "/api/v1/analytics/events").json()
    usd = next(row for row in flow["totals"] if row["currency"] == "USD")
    assert Decimal(usd["confirmations"]) == net_before + Decimal(other["net_sales"])
    assert Decimal(usd["edit_deltas"]) == net_after - net_before
    assert Decimal(usd["cancellations"]) == -Decimal(other["net_sales"])
    assert Decimal(usd["net_effect"]) == net_after  # what remains after the cancellation
    month = datetime.now(BEIRUT).strftime("%Y-%m")
    assert flow["monthly"] == [{"currency": "USD", "month": month, "net_effect": usd["net_effect"]}]
    # Current state agrees: sales = the edited invoice's current net_sales only.
    current = _get(client, tenant, token, "/api/v1/analytics/overview").json()
    assert Decimal(_amount(current["invoiced_sales"], "USD")) == net_after


def test_profit_uses_only_the_sale_time_snapshot_and_reports_uncovered_lines(
    client, session_factory
):
    owner, tenant, token = _owner_context(client, session_factory, "p8profit")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "4")
    before = _get(client, tenant, token, "/api/v1/analytics/overview").json()["gross_profit"][0]
    # A later, much cheaper actual purchase must not rewrite historical profit (D-067).
    supplier_id = client.get(f"/api/v1/suppliers?tenant_id={tenant}", headers=_auth(token)).json()[
        "suppliers"
    ][0]["id"]
    bought = _post(
        client,
        tenant,
        token,
        "/api/v1/supplier-purchases",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_id,
            "currency": "USD",
            "items": [{"product_id": product["id"], "quantity": "10", "unit_cost": "1.0000"}],
        },
    )
    assert bought.status_code == 201, bought.text
    after = _get(client, tenant, token, "/api/v1/analytics/overview").json()["gross_profit"][0]
    assert after == before
    # A line whose snapshot is missing is a data-integrity finding: uncovered, never estimated.
    # Confirmed rows are immutable at the database, so a legacy-style line without a snapshot is
    # appended to the current revision the way an old import would have left it.
    with session_factory() as db:
        invoice = db.get(Invoice, UUID(confirmed["id"]))
        assert invoice is not None
        db.add(
            InvoiceRevisionItem(
                tenant_id=UUID(tenant),
                invoice_revision_id=invoice.current_revision_id,
                line_number=99,
                tenant_product_id=None,
                product_name="Legacy line",
                media_snapshot={},
                quantity=Decimal("1"),
                price_basis="PIECE",
                normal_unit_price=Decimal("5"),
                grade_rule_snapshot={},
                effective_unit_price=Decimal("5"),
                line_discount=Decimal("0"),
                line_markup=Decimal("0"),
                line_total=Decimal("5"),
            )
        )
        db.commit()
    broken = _get(client, tenant, token, "/api/v1/analytics/overview").json()["gross_profit"][0]
    assert broken["uncovered_lines"] == 1 and broken["covered_lines"] == before["covered_lines"]
    assert broken["total_lines"] == before["total_lines"] + 1
    assert Decimal(broken["coverage_percent"]) < Decimal("100")
    assert broken["gross_profit"] == before["gross_profit"]  # the uncovered line adds nothing


def test_tenant_calendar_boundary_decides_period_membership(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p8tz")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    inside = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    outside = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    period = resolve_period("30d")
    assert period.start is not None
    with session_factory() as db:
        a = db.get(Invoice, UUID(inside["id"]))
        b = db.get(Invoice, UUID(outside["id"]))
        assert a is not None and b is not None
        a.confirmed_at = period.start + timedelta(minutes=30)  # 00:30 Beirut on the first day
        b.confirmed_at = period.start - timedelta(minutes=30)  # 23:30 Beirut the day before
        db.commit()
    body = _get(client, tenant, token, "/api/v1/analytics/overview").json()
    assert body["confirmed_invoices"] == 1
    everything = client.get(
        f"/api/v1/analytics/overview?tenant_id={tenant}&period=all", headers=_auth(token)
    ).json()
    assert everything["confirmed_invoices"] == 2
