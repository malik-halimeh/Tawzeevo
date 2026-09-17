"""FA-004 regression: a fresh owner provisions suppliers and product costs through the supported
API and reaches confirmed catalog and manual invoices without fixture inserts (D-041, D-034)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from test_invoice_editor import _auth, _catalog, _confirmable_payload, _owner_context

from tawzeevo_api.models import AuditEvent, InvoiceRevisionItem


def _post(client, tenant, token, path, json):
    return client.post(f"{path}?tenant_id={tenant}", headers=_auth(token), json=json)


def test_fresh_owner_provisions_costs_and_confirms_catalog_and_manual_invoices(
    client, session_factory
):
    _owner, tenant, token = _owner_context(client, session_factory, "fa004")
    _category, product, customer = _catalog(client, tenant, token)
    headers = _auth(token)

    # Without any supplier/cost, confirmation is still correctly blocked (D-034).
    draft = _post(
        client,
        tenant,
        token,
        "/api/v1/invoices",
        _confirmable_payload(customer["id"], product["id"]),
    ).json()
    blocked = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{draft['id']}/confirm",
        {"expected_revision_id": draft["current_revision_id"]},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "INVOICE_COST_REQUIRED"

    # Supported setup path: create a supplier, append a cost, preferred supplier follows.
    assert client.get(f"/api/v1/suppliers?tenant_id={tenant}", headers=headers).json() == {
        "suppliers": []
    }
    supplier = _post(client, tenant, token, "/api/v1/suppliers", {"name": "  Bekaa Wholesale "})
    assert supplier.status_code == 201, supplier.text
    assert supplier.json()["name"] == "Bekaa Wholesale"
    duplicate = _post(client, tenant, token, "/api/v1/suppliers", {"name": "bekaa wholesale"})
    assert duplicate.status_code == 409, duplicate.text
    renamed = client.patch(
        f"/api/v1/suppliers/{supplier.json()['id']}?tenant_id={tenant}",
        headers=headers,
        json={"name": "Bekaa Wholesale Co."},
    )
    assert renamed.status_code == 200, renamed.text

    mismatch = _post(
        client,
        tenant,
        token,
        f"/api/v1/suppliers/products/{product['id']}/costs",
        {
            "supplier_id": supplier.json()["id"],
            "unit_cost": "8.0000",
            "currency": "LBP",
            "cost_basis": "PIECE",
        },
    )
    assert mismatch.status_code == 400, mismatch.text
    assert mismatch.json()["detail"]["code"] == "CURRENCY_MISMATCH"

    cost = _post(
        client,
        tenant,
        token,
        f"/api/v1/suppliers/products/{product['id']}/costs",
        {
            "supplier_id": supplier.json()["id"],
            "unit_cost": "8.0000",
            "currency": "USD",
            "cost_basis": "PIECE",
            "effective_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "notes": "Quoted by phone",
        },
    )
    assert cost.status_code == 201, cost.text
    setup = cost.json()
    assert setup["preferred_supplier_id"] == supplier.json()["id"]
    assert [entry["unit_cost"] for entry in setup["entries"]] == ["8.0000"]
    assert setup["entries"][0]["source_type"] == "MANUAL"

    # Cost entries are append-only: a second entry never rewrites the first.
    newer = _post(
        client,
        tenant,
        token,
        f"/api/v1/suppliers/products/{product['id']}/costs",
        {
            "supplier_id": supplier.json()["id"],
            "unit_cost": "8.5000",
            "currency": "USD",
            "cost_basis": "PIECE",
        },
    )
    assert newer.status_code == 201, newer.text
    assert [entry["unit_cost"] for entry in newer.json()["entries"]] == ["8.5000", "8.0000"]

    # Invoice entry preloads the latest eligible cost of the preferred supplier.
    options = client.get(
        f"/api/v1/invoices/products/{product['id']}/cost-options?tenant_id={tenant}"
        "&currency=USD&basis=PIECE",
        headers=headers,
    ).json()["options"]
    assert options[0]["is_preferred"] is True and options[0]["unit_cost"] == "8.5000"

    # The same draft now confirms; its line snapshots the provisioned cost provenance.
    payload = _confirmable_payload(
        customer["id"], product["id"], predecessor_id=draft["current_revision_id"]
    )
    saved = client.put(
        f"/api/v1/invoices/{draft['id']}?tenant_id={tenant}", headers=headers, json=payload
    )
    assert saved.status_code == 200, saved.text
    confirmed = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{draft['id']}/confirm",
        {"expected_revision_id": saved.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED"
    with session_factory() as db:
        item = db.scalar(
            select(InvoiceRevisionItem).where(
                InvoiceRevisionItem.invoice_revision_id == confirmed.json()["current_revision_id"]
            )
        )
        assert item is not None
        assert str(item.unit_cost) == "8.5000"
        assert str(item.supplier_id) == supplier.json()["id"]
        assert item.cost_source_type == "MANUAL" and item.is_cost_override is False
        actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.tenant_id == tenant)))
        assert {"supplier_created", "supplier_renamed", "product_cost_appended"} <= actions

    # A manual (non-catalog) line confirms with an explicit supplier and reasoned cost override.
    manual = _post(
        client,
        tenant,
        token,
        "/api/v1/invoices",
        {
            "client_command_id": str(uuid4()),
            "customer_id": customer["id"],
            "currency": "USD",
            "items": [
                {
                    "manual_name": "Ice bags",
                    "manual_unit_price": "3.0000",
                    "quantity_expression": "2",
                    "price_basis": "PIECE",
                    "supplier_id": supplier.json()["id"],
                    "cost_override": "1.2500",
                    "cost_override_reason": "Cash purchase at the market",
                }
            ],
        },
    )
    assert manual.status_code == 201, manual.text
    manual_confirmed = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{manual.json()['id']}/confirm",
        {"expected_revision_id": manual.json()["current_revision_id"]},
    )
    assert manual_confirmed.status_code == 200, manual_confirmed.text

    # Preferred supplier can be changed or cleared explicitly.
    cleared = client.put(
        f"/api/v1/suppliers/products/{product['id']}/preferred-supplier?tenant_id={tenant}",
        headers=headers,
        json={"supplier_id": None},
    )
    assert cleared.status_code == 200 and cleared.json()["preferred_supplier_id"] is None


def test_supplier_setup_is_owner_only_and_tenant_private(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "fa004-a")
    _, other_tenant, other_token = _owner_context(client, session_factory, "fa004-b")
    _category, product, _customer = _catalog(client, tenant, token)
    supplier = _post(client, tenant, token, "/api/v1/suppliers", {"name": "Private supplier"})
    assert supplier.status_code == 201
    # Another tenant's owner cannot see or use this tenant's supplier/product.
    assert client.get(
        f"/api/v1/suppliers?tenant_id={other_tenant}", headers=_auth(other_token)
    ).json() == {"suppliers": []}
    assert (
        client.get(f"/api/v1/suppliers?tenant_id={tenant}", headers=_auth(other_token)).status_code
        == 403
    )
    foreign_cost = _post(
        client,
        other_tenant,
        other_token,
        f"/api/v1/suppliers/products/{product['id']}/costs",
        {
            "supplier_id": supplier.json()["id"],
            "unit_cost": "1.0000",
            "currency": "USD",
            "cost_basis": "PIECE",
        },
    )
    assert foreign_cost.status_code == 404, foreign_cost.text
