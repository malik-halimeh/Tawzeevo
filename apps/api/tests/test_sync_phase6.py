"""Phase 6 P6-M5: supplier, price-append, procurement-edit, purchase and supplier-payment commands
ride the Phase 4 sync protocol unchanged (PHASE_06.md I) — idempotent, versioned, price-free
projection for suppliers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import _attach_latest_cost, _auth, _catalog
from test_procurement import _confirm_invoice, _today
from test_sync_push import _device, _op, _push

from tawzeevo_api.models import SupplierPurchase, TenantProductCostEntry, TenantSupplier


def _get(client, tenant, token, path):
    return client.get(f"{path}?tenant_id={tenant}", headers=_auth(token))


def test_supplier_commands_apply_once_and_pull_carries_no_costs(client, session_factory):
    owner, tenant, token, device = _device(client, session_factory, "p6sync")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    supplier_id = str(uuid4())
    create = _op(
        "supplier",
        "create",
        supplier_id,
        {"name": "Offline Wholesale", "contact_phone": "03 555 111", "address": "Chtaura"},
    )
    first = _push(client, tenant, token, device, [create])
    assert first.status_code == 200, first.text
    result = first.json()["results"][0]
    assert result["status"] == "applied" and result["version"] == 1
    assert result["projection"]["contact_phone"] == "+9613555111"
    assert "cost" not in first.text.lower()
    replay = _push(client, tenant, token, device, [create]).json()["results"][0]
    assert replay["status"] == "applied" and replay["replayed"] is True
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(TenantSupplier)
                .where(TenantSupplier.tenant_id == UUID(tenant))
            )
            == 1
        )

    # Versioned update: a stale expected version is a conflict envelope, never an overwrite.
    update = _op("supplier", "update", supplier_id, {"address": "Zahle"}, expected_version=1)
    applied = _push(client, tenant, token, device, [update]).json()["results"][0]
    assert applied["status"] == "applied" and applied["version"] == 2
    stale = _op("supplier", "update", supplier_id, {"address": "Beirut"}, expected_version=1)
    conflict = _push(client, tenant, token, device, [stale]).json()["results"][0]
    assert conflict["status"] == "conflict" and conflict["conflict"]["server_version"] == 2
    assert conflict["conflict"]["server_projection"]["address"] == "Zahle"

    # Price append offline: the operation id names the row, so a replay never appends twice.
    entry_id = str(uuid4())
    cost = _op(
        "product_cost",
        "create",
        entry_id,
        {
            "product_id": product["id"],
            "supplier_id": supplier_id,
            "unit_cost": "8.2500",
            "currency": "USD",
            "cost_basis": "PIECE",
            "source_type": "QUOTE",
        },
        operation_id=entry_id,
    )
    appended = _push(client, tenant, token, device, [cost]).json()["results"][0]
    assert appended["status"] == "applied", appended
    assert appended["projection"]["source_type"] == "QUOTE"
    _push(client, tenant, token, device, [cost])
    with session_factory() as db:
        rows = db.scalars(
            select(TenantProductCostEntry).where(TenantProductCostEntry.tenant_id == UUID(tenant))
        ).all()
        assert len(rows) == 1 and rows[0].id == UUID(entry_id)
    fake = _op(
        "product_cost",
        "create",
        str(uuid4()),
        {
            "product_id": product["id"],
            "supplier_id": supplier_id,
            "unit_cost": "1",
            "currency": "USD",
            "cost_basis": "PIECE",
            "source_type": "ACTUAL_PURCHASE",
        },
    )
    assert _push(client, tenant, token, device, [fake]).json()["results"][0]["status"] == "rejected"

    # The change feed carries the supplier (identity/contact/location) and nothing about prices.
    pulled = client.get(
        f"/api/v1/sync/pull?tenant_id={tenant}&cursor=0&device_installation_id={device}",
        headers=_auth(token),
    )
    assert pulled.status_code == 200, pulled.text
    kinds = {change["entity_type"] for change in pulled.json()["changes"]}
    assert "supplier" in kinds and "product_cost" not in kinds
    supplier_change = next(c for c in pulled.json()["changes"] if c["entity_type"] == "supplier")
    assert "unit_cost" not in supplier_change["payload"]


def test_procurement_edit_purchase_and_supplier_payment_through_sync(client, session_factory):
    owner, tenant, token, device = _device(client, session_factory, "p6sync2")
    _category, product, customer = _catalog(client, tenant, token, name="Labneh")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "5")
    created = client.post(
        f"/api/v1/procurement/lists?tenant_id={tenant}",
        headers=_auth(token),
        json={"demand_from": _today(), "demand_to": _today()},
    ).json()
    list_id, item = created["id"], created["items"][0]

    # Procurement edit offline with the expected version.
    edit = _op(
        "procurement_item", "update", item["id"], {"target_quantity": "7"}, expected_version=1
    )
    edited = _push(client, tenant, token, device, [edit]).json()["results"][0]
    assert edited["status"] == "applied" and edited["projection"]["target_quantity"] == "7.0000"
    assert edited["projection"]["required_quantity"] == "5.0000"
    again = _push(client, tenant, token, device, [edit]).json()["results"][0]
    assert again["replayed"] is True
    stale = _op(
        "procurement_item", "update", item["id"], {"target_quantity": "9"}, expected_version=1
    )
    assert (
        _push(client, tenant, token, device, [stale]).json()["results"][0]["status"] == "conflict"
    )

    # Supplier purchase as a financial command: the operation id is the idempotency key.
    purchase_op = _op(
        "supplier_purchase",
        "create",
        str(uuid4()),
        {
            "supplier_id": item["supplier_id"],
            "currency": "USD",
            "procurement_list_id": list_id,
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": "7",
                    "unit_cost": "7.9000",
                    "procurement_item_id": item["id"],
                }
            ],
        },
    )
    bought = _push(client, tenant, token, device, [purchase_op]).json()["results"][0]
    assert bought["status"] == "applied", bought
    assert bought["projection"]["total_amount"] == "55.3000"
    replayed = _push(client, tenant, token, device, [purchase_op]).json()["results"][0]
    assert replayed["status"] == "applied" and replayed["replayed"] is True
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SupplierPurchase)
                .where(SupplierPurchase.tenant_id == UUID(tenant))
            )
            == 1
        )
    detail = _get(client, tenant, token, f"/api/v1/procurement/lists/{list_id}").json()
    assert detail["status"] == "COMPLETE" and detail["items"][0]["purchased_quantity"] == "7.0000"
    balances = _get(
        client, tenant, token, f"/api/v1/supplier-ledger/{item['supplier_id']}/balances"
    ).json()
    assert balances["balances"] == [{"currency": "USD", "balance": "55.3000"}]

    # Supplier payment as a financial command, capped by the payable (D-039) like online.
    over = _op(
        "supplier_payment",
        "receipt",
        str(uuid4()),
        {
            "supplier_id": item["supplier_id"],
            "currency": "USD",
            "amount": "60",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert _push(client, tenant, token, device, [over]).json()["results"][0]["status"] == "rejected"
    pay = _op(
        "supplier_payment",
        "receipt",
        str(uuid4()),
        {
            "supplier_id": item["supplier_id"],
            "currency": "USD",
            "amount": "25",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    paid = _push(client, tenant, token, device, [pay]).json()["results"][0]
    assert paid["status"] == "applied", paid
    _push(client, tenant, token, device, [pay])
    balances = _get(
        client, tenant, token, f"/api/v1/supplier-ledger/{item['supplier_id']}/balances"
    ).json()
    assert balances["balances"] == [{"currency": "USD", "balance": "30.3000"}]
