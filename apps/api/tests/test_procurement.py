"""Phase 6 P6-M3: demand-driven procurement, quantity meanings, D-058 lifecycle, carry-forward,
neutral assignee and the price-free runner projection (PHASE_06.md A/E/F)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import inspect, select
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _login,
    _owner_context,
    _user,
)

from tawzeevo_api.models import (
    ProcurementItem,
    SystemUserType,
    TenantMembership,
    TenantRole,
)

STOCK_WORDS = re.compile(r"stock|inventory|on_hand|on hand|reserved|warehouse|availability", re.I)


def _post(client, tenant, token, path, json=None):
    return client.post(f"{path}?tenant_id={tenant}", headers=_auth(token), json=json)


def _get(client, tenant, token, path):
    return client.get(f"{path}?tenant_id={tenant}", headers=_auth(token))


def _confirm_invoice(client, tenant, token, customer_id, product_id, quantity_expression="1 + 1"):
    payload = _confirmable_payload(customer_id, product_id)
    payload["items"][0]["quantity_expression"] = quantity_expression  # type: ignore[index]
    draft = _post(client, tenant, token, "/api/v1/invoices", payload)
    assert draft.status_code == 201, draft.text
    confirmed = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{draft.json()['id']}/confirm",
        {"expected_revision_id": draft.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def test_no_inventory_columns_exist_anywhere(session_factory):
    """PHASE_06.md A: none of the forbidden concepts exists as a column on any table."""
    with session_factory() as db:
        inspector = inspect(db.get_bind())
        for table in inspector.get_table_names():
            for column in inspector.get_columns(table):
                assert not STOCK_WORDS.search(column["name"]), f"{table}.{column['name']}"


def test_demand_generation_quantities_edits_and_lifecycle(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p6proc")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    # Two confirmed invoices (2 + 3 pieces) and one draft that must never count.
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "3")
    draft = _post(
        client,
        tenant,
        token,
        "/api/v1/invoices",
        _confirmable_payload(customer["id"], product["id"]),
    )
    assert draft.status_code == 201

    empty = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": "2020-01-01", "demand_to": "2020-01-02"},
    )
    assert empty.status_code == 409 and empty.json()["detail"]["code"] == "NO_CONFIRMED_DEMAND"
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today(), "notes": "Friday run"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    list_id = body["id"]
    assert body["status"] == "OPEN" and len(body["items"]) == 1
    line = body["items"][0]
    assert line["origin"] == "DEMAND" and line["demand_invoice_count"] == 2
    assert line["required_quantity"] == "5.0000" and line["target_quantity"] == "5.0000"
    assert line["purchased_quantity"] == "0.0000" and line["remaining_quantity"] == "5.0000"
    assert line["supplier_name"] == "Confirmation Supplier"  # preferred supplier preselected
    assert line["estimate"] is not None and line["estimate"]["unit_cost"] == "8.0000"
    assert line["estimate"]["remaining_cost"] == "40.0000"
    assert body["estimated_totals"] == {"USD": "40.0000"}
    assert not STOCK_WORDS.search(created.text)

    # Target edits never touch the demand figure; a stale version is refused.
    edited = client.patch(
        f"/api/v1/procurement/lists/{list_id}/items/{line['id']}?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_version": 1, "target_quantity": "8", "notes": "round up to a box"},
    )
    assert edited.status_code == 200, edited.text
    line = edited.json()["items"][0]
    assert line["required_quantity"] == "5.0000" and line["target_quantity"] == "8.0000"
    assert line["remaining_quantity"] == "8.0000" and line["version"] == 2
    stale = client.patch(
        f"/api/v1/procurement/lists/{list_id}/items/{line['id']}?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_version": 1, "target_quantity": "9"},
    )
    assert stale.status_code == 409

    # A manual line, then removing it keeps it readable with the reason (nothing is deleted).
    _category2, product2, _customer2 = _catalog(
        client, tenant, token, name="Olive Oil", barcode="5280000000029"
    )
    manual = _post(
        client,
        tenant,
        token,
        f"/api/v1/procurement/lists/{list_id}/items",
        {"product_id": product2["id"], "target_quantity": "4"},
    )
    assert manual.status_code == 200, manual.text
    manual_line = next(i for i in manual.json()["items"] if i["origin"] == "MANUAL")
    assert manual_line["required_quantity"] == "0.0000" and manual_line["estimate"] is None
    removed = _post(
        client,
        tenant,
        token,
        f"/api/v1/procurement/lists/{list_id}/items/{manual_line['id']}/remove",
        {"reason": "already bought yesterday"},
    )
    assert removed.status_code == 200
    kept = next(i for i in removed.json()["items"] if i["id"] == manual_line["id"])
    assert kept["remove_reason"] == "already bought yesterday" and kept["removed_at"]
    with session_factory() as db:
        assert db.get(ProcurementItem, UUID(manual_line["id"])) is not None

    # Completion is refused while a line is open; waiving with a reason settles it.
    blocked = _post(client, tenant, token, f"/api/v1/procurement/lists/{list_id}/complete")
    assert (
        blocked.status_code == 409 and blocked.json()["detail"]["code"] == "PROCUREMENT_LINES_OPEN"
    )
    waived = _post(
        client,
        tenant,
        token,
        f"/api/v1/procurement/lists/{list_id}/items/{line['id']}/waive",
        {"reason": "supplier closed this week"},
    )
    assert waived.status_code == 200
    done = _post(client, tenant, token, f"/api/v1/procurement/lists/{list_id}/complete")
    assert done.status_code == 200 and done.json()["status"] == "COMPLETE"
    closed = client.patch(
        f"/api/v1/procurement/lists/{list_id}/items/{line['id']}?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_version": 3, "target_quantity": "1"},
    )
    assert (
        closed.status_code == 409 and closed.json()["detail"]["code"] == "PROCUREMENT_LIST_CLOSED"
    )

    # Export: demand/progress columns and the labelled estimate, no stock column.
    export = _get(client, tenant, token, f"/api/v1/procurement/lists/{list_id}/export.csv")
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    header = export.text.splitlines()[0]
    assert header.startswith("product,supplier,unit,required,target,purchased,remaining,state")
    assert not STOCK_WORDS.search(export.text)
    assert "waived" in export.text and "removed" in export.text

    # Cancelled invoices never count as demand.
    cancelled_only = _get(client, tenant, token, "/api/v1/procurement/lists")
    assert cancelled_only.status_code == 200 and len(cancelled_only.json()["lists"]) == 1


def test_carry_forward_partial_and_cancel_rules(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p6carry")
    _category, product, customer = _catalog(client, tenant, token, name="Labneh")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "6")
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today()},
    ).json()
    list_id, item_id = created["id"], created["items"][0]["id"]
    # Simulate a partial purchase the way P6-M4 will write it: purchased 2 of 6.
    with session_factory() as db:
        item = db.get(ProcurementItem, UUID(item_id))
        assert item is not None
        item.purchased_quantity = Decimal("2")
        db.commit()
    # Cancelling a list with purchases is refused; carry-forward moves the remaining 4.
    cancel = _post(
        client, tenant, token, f"/api/v1/procurement/lists/{list_id}/cancel", {"reason": "x"}
    )
    assert cancel.status_code == 409
    below = client.patch(
        f"/api/v1/procurement/lists/{list_id}/items/{item_id}?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_version": 1, "target_quantity": "1"},
    )
    assert below.status_code == 422 and below.json()["detail"]["code"] == "TARGET_BELOW_PURCHASED"
    carried = _post(
        client,
        tenant,
        token,
        f"/api/v1/procurement/lists/{list_id}/carry-forward",
        {"title": "Monday"},
    )
    assert carried.status_code == 201, carried.text
    new = carried.json()
    assert new["title"] == "Monday" and new["carried_from_list_id"] == list_id
    assert new["status"] == "OPEN" and len(new["items"]) == 1
    new_line = new["items"][0]
    assert new_line["origin"] == "CARRY_FORWARD" and new_line["required_quantity"] == "4.0000"
    assert new_line["target_quantity"] == "4.0000" and new_line["carried_from_item_id"] == item_id
    source = _get(client, tenant, token, f"/api/v1/procurement/lists/{list_id}").json()
    assert source["status"] == "COMPLETE"
    assert source["items"][0]["carried_to_item_id"] == new_line["id"]
    assert source["items"][0]["purchased_quantity"] == "2.0000"  # history untouched
    again = _post(client, tenant, token, f"/api/v1/procurement/lists/{list_id}/carry-forward", {})
    assert again.status_code == 409  # a complete list cannot be carried twice

    # A fresh list with no purchases can be cancelled with a reason.
    fresh = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today()},
    ).json()
    cancelled = _post(
        client,
        tenant,
        token,
        f"/api/v1/procurement/lists/{fresh['id']}/cancel",
        {"reason": "duplicate"},
    )
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancel_reason"] == "duplicate"


def test_assignee_is_neutral_and_driver_projection_has_no_prices(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p6assign")
    _category, product, customer = _catalog(client, tenant, token, name="Jam")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "5")
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today()},
    ).json()
    list_id = created["id"]

    # Sole owner: the only assignee is the owner themself; self-assignment works.
    assignees = _get(client, tenant, token, "/api/v1/procurement/assignees").json()["assignees"]
    assert len(assignees) == 1 and assignees[0]["role"] == "owner" and assignees[0]["is_self"]
    own = client.put(
        f"/api/v1/procurement/lists/{list_id}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"membership_id": assignees[0]["membership_id"]},
    )
    assert own.status_code == 200 and own.json()["assignee"]["is_self"] is True
    mine = _get(client, tenant, token, "/api/v1/procurement/my-pickups").json()
    assert [row["list_id"] for row in mine["lists"]] == [list_id]

    # An active driver membership becomes assignable; an inactive one is not.
    driver = _user(session_factory, "driver-p6assign@example.com", SystemUserType.CLIENT)
    with session_factory() as db:
        membership = TenantMembership(
            tenant_id=UUID(tenant), user_id=driver.id, role=TenantRole.DRIVER, is_active=True
        )
        db.add(membership)
        db.commit()
        driver_membership_id = membership.id
    driver_token = _login(client, driver.email)
    assigned = client.put(
        f"/api/v1/procurement/lists/{list_id}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"membership_id": str(driver_membership_id)},
    )
    assert assigned.status_code == 200 and assigned.json()["assignee"]["role"] == "driver"
    unknown = client.put(
        f"/api/v1/procurement/lists/{list_id}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"membership_id": str(uuid4())},
    )
    assert unknown.status_code == 404

    # Driver: pickup projection only — supplier identity and quantities, never a price.
    pickups = _get(client, tenant, driver_token, "/api/v1/procurement/my-pickups")
    assert pickups.status_code == 200, pickups.text
    payload = pickups.json()
    assert len(payload["lists"]) == 1
    supplier = payload["lists"][0]["suppliers"][0]
    assert supplier["supplier_name"] == "Confirmation Supplier"
    assert supplier["items"][0]["remaining_quantity"] == "5.0000"
    # `price_basis` is the unit name (PIECE/BOX); no money field may appear.
    assert not re.search(r"cost|unit_price|estimate|margin|profit|currency", pickups.text, re.I)
    # Driver cannot open owner procurement views, price history or supplier setup.
    for path in (
        f"/api/v1/procurement/lists/{list_id}",
        "/api/v1/procurement/lists",
        f"/api/v1/supplier-prices/products/{product['id']}",
        "/api/v1/suppliers",
    ):
        assert _get(client, tenant, driver_token, path).status_code == 403, path
    # A list assigned to someone else is not in the driver's projection.
    back = client.put(
        f"/api/v1/procurement/lists/{list_id}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"membership_id": None},
    )
    assert back.status_code == 200 and back.json()["assignee"] is None
    assert _get(client, tenant, driver_token, "/api/v1/procurement/my-pickups").json() == {
        "lists": []
    }

    # Another business and a platform admin see nothing.
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p6assign2")
    assert (
        _get(client, other_tenant, other_token, f"/api/v1/procurement/lists/{list_id}").status_code
        == 404
    )
    admin = _user(session_factory, "admin-p6assign-x@example.com", SystemUserType.ADMIN)
    admin_token = _login(client, admin.email)
    assert _get(client, tenant, admin_token, "/api/v1/procurement/lists").status_code == 403
    with session_factory() as db:
        assert db.scalar(
            select(ProcurementItem.id).where(ProcurementItem.tenant_id == UUID(tenant))
        )
