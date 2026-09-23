"""Phase 6 P6-M4: actual supplier purchases — atomic history/ledger/procurement effects,
rollback, replay, reversal, payable-capped payments, totals by currency (PHASE_06.md G/H)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice, _today

from tawzeevo_api.models import (
    ProcurementItem,
    SupplierLedgerEntry,
    SupplierPurchase,
    SupplierPurchaseItem,
    TenantProductCostEntry,
)


def _post(client, tenant, token, path, json=None):
    return client.post(f"{path}?tenant_id={tenant}", headers=_auth(token), json=json)


def _get(client, tenant, token, path):
    return client.get(f"{path}?tenant_id={tenant}", headers=_auth(token))


def _count(session_factory, model, tenant):
    with session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(model).where(model.tenant_id == UUID(tenant))
        )


def _balance(client, tenant, token, supplier_id):
    body = _get(client, tenant, token, f"/api/v1/supplier-ledger/{supplier_id}/balances").json()
    return {row["currency"]: row["balance"] for row in body["balances"]}


def test_purchase_finalization_is_atomic_replay_safe_and_rolls_back(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p6buy")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])  # supplier + 8.0000 cost
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "6")
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today()},
    ).json()
    list_id, item = created["id"], created["items"][0]
    supplier_id = item["supplier_id"]
    assert supplier_id and _balance(client, tenant, token, supplier_id) == {}

    # A bad second line rolls the whole purchase back: no header, no line, no cost, no ledger.
    bad = _post(
        client,
        tenant,
        token,
        "/api/v1/supplier-purchases",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_id,
            "currency": "USD",
            "procurement_list_id": list_id,
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": "4",
                    "unit_cost": "7.5000",
                    "procurement_item_id": item["id"],
                },
                {"product_id": str(uuid4()), "quantity": "1", "unit_cost": "1"},
            ],
        },
    )
    assert bad.status_code == 404, bad.text
    assert _count(session_factory, SupplierPurchase, tenant) == 0
    assert _count(session_factory, SupplierPurchaseItem, tenant) == 0
    assert _count(session_factory, SupplierLedgerEntry, tenant) == 0
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(TenantProductCostEntry)
                .where(TenantProductCostEntry.source_type == "ACTUAL_PURCHASE")
            )
            == 0
        )
        row = db.get(ProcurementItem, UUID(item["id"]))
        assert row is not None and row.purchased_quantity == 0

    # Currency must match the product currency (no silent conversion).
    wrong = _post(
        client,
        tenant,
        token,
        "/api/v1/supplier-purchases",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_id,
            "currency": "EUR",
            "items": [{"product_id": product["id"], "quantity": "1", "unit_cost": "1"}],
        },
    )
    assert wrong.status_code == 400 and wrong.json()["detail"]["code"] == "CURRENCY_MISMATCH"

    # The real purchase: 4 of the 6 demanded, at 7.5 → payable 30, history row, list partly done.
    key = str(uuid4())
    body = {
        "idempotency_key": key,
        "supplier_id": supplier_id,
        "currency": "USD",
        "procurement_list_id": list_id,
        "supplier_reference": "INV-778",
        "items": [
            {
                "product_id": product["id"],
                "quantity": "4",
                "unit_cost": "7.5000",
                "procurement_item_id": item["id"],
            }
        ],
    }
    first = _post(client, tenant, token, "/api/v1/supplier-purchases", body)
    assert first.status_code == 201, first.text
    purchase = first.json()
    assert purchase["total_amount"] == "30.0000" and purchase["replayed"] is False
    assert purchase["items"][0]["line_total"] == "30.0000"
    assert purchase["items"][0]["cost_entry_id"]
    assert _balance(client, tenant, token, supplier_id) == {"USD": "30.0000"}
    replay = _post(client, tenant, token, "/api/v1/supplier-purchases", body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == purchase["id"]
    assert replay.json()["replayed"] is True
    assert _count(session_factory, SupplierPurchase, tenant) == 1
    assert _balance(client, tenant, token, supplier_id) == {"USD": "30.0000"}  # charged once
    conflict = _post(
        client,
        tenant,
        token,
        "/api/v1/supplier-purchases",
        {**body, "supplier_reference": "x", "items": [{**body["items"][0], "quantity": "5"}]},
    )
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    )

    # Price history: the actual purchase is the newest row and now drives invoice preload.
    history = _get(
        client, tenant, token, f"/api/v1/suppliers/products/{product['id']}/costs"
    ).json()
    assert history["entries"][0]["source_type"] == "ACTUAL_PURCHASE"
    assert history["entries"][0]["unit_cost"] == "7.5000"
    assert history["entries"][0]["quantity_context"] == "4.0000"
    insight = _get(
        client, tenant, token, f"/api/v1/supplier-prices/products/{product['id']}"
    ).json()
    assert insight["insights"][0]["last_purchase_unit_cost"] == "7.5000"

    # Procurement progress: purchased 4, remaining 2, status PARTIALLY_PURCHASED.
    detail = _get(client, tenant, token, f"/api/v1/procurement/lists/{list_id}").json()
    assert detail["status"] == "PARTIALLY_PURCHASED"
    line = detail["items"][0]
    assert line["purchased_quantity"] == "4.0000" and line["remaining_quantity"] == "2.0000"
    assert line["required_quantity"] == "6.0000"  # demand untouched

    # Second purchase completes the line and the list automatically.
    second = _post(
        client,
        tenant,
        token,
        "/api/v1/supplier-purchases",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_id,
            "currency": "USD",
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": "2",
                    "unit_cost": "7.6000",
                    "procurement_item_id": item["id"],
                }
            ],
        },
    )
    assert second.status_code == 201, second.text
    detail = _get(client, tenant, token, f"/api/v1/procurement/lists/{list_id}").json()
    assert detail["status"] == "COMPLETE" and detail["items"][0]["remaining_quantity"] == "0.0000"
    assert _balance(client, tenant, token, supplier_id) == {"USD": "45.2000"}

    # No stock row anywhere: the only quantities are demand and progress.
    assert "stock" not in first.text.lower() and "inventory" not in detail.__repr__().lower()

    # Reversal of the second purchase: compensating entry, progress back, list reopens.
    reverse_key = str(uuid4())
    reversed_ = _post(
        client,
        tenant,
        token,
        f"/api/v1/supplier-purchases/{second.json()['id']}/reverse",
        {"idempotency_key": reverse_key, "reason": "returned damaged goods"},
    )
    assert reversed_.status_code == 200, reversed_.text
    assert (
        reversed_.json()["reversed_at"]
        and reversed_.json()["reversal_reason"] == "returned damaged goods"
    )
    assert _balance(client, tenant, token, supplier_id) == {"USD": "30.0000"}
    detail = _get(client, tenant, token, f"/api/v1/procurement/lists/{list_id}").json()
    assert detail["status"] == "PARTIALLY_PURCHASED"
    assert detail["items"][0]["purchased_quantity"] == "4.0000"
    again = _post(
        client,
        tenant,
        token,
        f"/api/v1/supplier-purchases/{second.json()['id']}/reverse",
        {"idempotency_key": reverse_key, "reason": "returned damaged goods"},
    )
    assert again.status_code == 200  # same key replays
    twice = _post(
        client,
        tenant,
        token,
        f"/api/v1/supplier-purchases/{second.json()['id']}/reverse",
        {"idempotency_key": str(uuid4()), "reason": "again"},
    )
    assert twice.status_code == 409
    with session_factory() as db:  # history is never rewritten by a reversal
        kept = db.scalar(
            select(func.count())
            .select_from(TenantProductCostEntry)
            .where(TenantProductCostEntry.source_type == "ACTUAL_PURCHASE")
        )
        assert kept == 2
        types = [
            row
            for row in db.scalars(
                select(SupplierLedgerEntry.entry_type).where(
                    SupplierLedgerEntry.tenant_id == UUID(tenant)
                )
            )
        ]
        assert sorted(types) == ["PURCHASE_CHARGE", "PURCHASE_CHARGE", "PURCHASE_REVERSAL"]

    # D-059 preload (audit finding on reversed purchases): the reversed second purchase (7.6000)
    # no longer drives the preload; the latest non-reversed actual purchase (7.5000) does.
    options = client.get(
        f"/api/v1/invoices/products/{product['id']}/cost-options",
        params={"tenant_id": tenant, "currency": "USD", "basis": "PIECE"},
        headers=_auth(token),
    )
    assert options.status_code == 200, options.text
    preload = [o for o in options.json()["options"] if o["supplier_id"] == supplier_id]
    assert preload and preload[0]["unit_cost"] == "7.5000", options.text

    # Immutable at the database (same guarantee as the other financial rows): purchase lines
    # reject any update/delete; a header rejects delete, any non-reversal update, and a second
    # reversal; the only accepted change is the reversal transition the service performs.
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    with session_factory() as db:
        db.execute(text("SELECT set_config('app.current_tenant_id', :t, true)"), {"t": tenant})
        for statement in (
            "UPDATE supplier_purchase_items SET quantity = quantity + 1 WHERE tenant_id = :t",
            "DELETE FROM supplier_purchase_items WHERE tenant_id = :t",
            "UPDATE supplier_purchases SET total_amount = 0 WHERE tenant_id = :t",
            "DELETE FROM supplier_purchases WHERE tenant_id = :t",
            # a reversal that also alters the purchase, and a second reversal of a reversed row
            "UPDATE supplier_purchases SET reversed_at = now(), reversal_idempotency_key = :k, "
            "total_amount = 1 WHERE tenant_id = :t AND reversed_at IS NULL",
            "UPDATE supplier_purchases SET reversal_reason = 'again' "
            "WHERE tenant_id = :t AND reversed_at IS NOT NULL",
        ):
            with pytest.raises(DBAPIError, match="immutable financial row"), db.begin_nested():
                db.execute(text(statement), {"t": tenant, "k": str(uuid4())})
        db.rollback()

    # Payments: an ordinary payment is capped at the payable (D-039); no per-purchase allocation.
    over = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/supplier-payments",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_id,
            "currency": "USD",
            "amount": "40",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert over.status_code == 409, over.text
    paid = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/supplier-payments",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_id,
            "currency": "USD",
            "amount": "10",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert paid.status_code == 201, paid.text
    assert _balance(client, tenant, token, supplier_id) == {"USD": "20.0000"}
    assert "purchase_id" not in paid.text  # payments are aggregate, never allocated

    # Listing and isolation.
    listed = _get(client, tenant, token, "/api/v1/supplier-purchases").json()["purchases"]
    assert [p["reversed_at"] is not None for p in listed] == [True, False]
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p6buy2")
    assert (
        _get(
            client, other_tenant, other_token, f"/api/v1/supplier-purchases/{purchase['id']}"
        ).status_code
        == 404
    )
    assert _get(client, other_tenant, other_token, "/api/v1/supplier-purchases").json() == {
        "purchases": []
    }


def test_outstanding_totals_by_currency_never_net_or_sum_across(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p6tot")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _category2, product_lbp, _c = _catalog(
        client, tenant, token, name="Bread", barcode="5280000000036", currency="LBP", price="90000"
    )
    supplier_a = _post(client, tenant, token, "/api/v1/suppliers", {"name": "A"}).json()["id"]
    supplier_b = _post(client, tenant, token, "/api/v1/suppliers", {"name": "B"}).json()["id"]
    # A: owed 100 USD; B: prepaid 40 USD (credit) and owed 500000 LBP.
    for supplier, currency, product_id, qty, cost in (
        (supplier_a, "USD", product["id"], "10", "10"),
        (supplier_b, "LBP", product_lbp["id"], "5", "100000"),
    ):
        r = _post(
            client,
            tenant,
            token,
            "/api/v1/supplier-purchases",
            {
                "idempotency_key": str(uuid4()),
                "supplier_id": supplier,
                "currency": currency,
                "items": [{"product_id": product_id, "quantity": qty, "unit_cost": cost}],
            },
        )
        assert r.status_code == 201, r.text
    prepaid = _post(
        client,
        tenant,
        token,
        "/api/v1/payments/supplier-prepayments",
        {
            "idempotency_key": str(uuid4()),
            "supplier_id": supplier_b,
            "currency": "USD",
            "amount": "40",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert prepaid.status_code == 201, prepaid.text
    # A confirmed customer invoice creates customer outstanding in USD.
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")

    totals = _get(client, tenant, token, "/api/v1/supplier-ledger/totals")
    assert totals.status_code == 200, totals.text
    body = totals.json()
    suppliers = {row["currency"]: row for row in body["suppliers"]}
    assert suppliers["USD"] == {
        "currency": "USD",
        "outstanding": "100.0000",
        "credit": "40.0000",
        "parties": 1,
    }
    assert suppliers["LBP"] == {
        "currency": "LBP",
        "outstanding": "500000.0000",
        "credit": "0.0000",
        "parties": 1,
    }
    customers = {row["currency"]: row for row in body["customers"]}
    assert Decimal(customers["USD"]["outstanding"]) > 0 and customers["USD"]["parties"] == 1
    assert "total" not in {k for row in body["suppliers"] for k in row} - {"outstanding"}
    # Nothing is summed across currencies: there is no grand total field at all.
    assert set(body) == {"customers", "suppliers"}
