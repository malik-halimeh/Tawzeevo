"""D-106: a runner's pickup report is not a purchase until the owner confirms it."""

from __future__ import annotations

from uuid import UUID, uuid4

from test_delivery_tasks import _driver
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice, _today
from test_supplier_purchases import _balance, _count, _get, _post

from tawzeevo_api.models import AuditEvent, PickupReport, ProcurementItem, SupplierPurchase

PATH = "/api/v1/procurement/pickup-reports"


def _assigned_list(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "6")
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today()},
    ).json()
    _user, driver_token, membership_id = _driver(
        client, session_factory, tenant, f"runner-{suffix}@example.com"
    )
    assigned = client.put(
        f"/api/v1/procurement/lists/{created['id']}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"membership_id": membership_id},
    )
    assert assigned.status_code == 200, assigned.text
    return tenant, token, driver_token, created["id"], created["items"][0]


def _report(item, list_id, key=None, quantity="4", unit_cost="7.5000"):
    return {
        "idempotency_key": key or str(uuid4()),
        "list_id": list_id,
        "supplier_id": item["supplier_id"],
        "currency": "USD",
        "lines": [
            {"procurement_item_id": item["id"], "quantity": quantity, "unit_cost": unit_cost}
        ],
    }


def test_report_then_owner_confirms_one_purchase(client, session_factory):
    tenant, token, driver_token, list_id, item = _assigned_list(client, session_factory, "pick1")
    key = str(uuid4())
    sent = _post(client, tenant, driver_token, PATH, _report(item, list_id, key))
    assert sent.status_code == 201, sent.text
    report = sent.json()
    assert report["status"] == "PENDING" and report["total"] == "30.0000"
    assert report["lines"][0]["product_name"] == "Cedar Water"
    # Replay returns the same report; the same key with other lines is a conflict.
    assert (
        _post(client, tenant, driver_token, PATH, _report(item, list_id, key)).json()["id"]
        == (report["id"])
    )
    conflict = _post(client, tenant, driver_token, PATH, _report(item, list_id, key, quantity="5"))
    assert conflict.status_code == 409
    # Nothing is purchased yet.
    assert _count(session_factory, SupplierPurchase, tenant) == 0
    assert _balance(client, tenant, token, item["supplier_id"]) == {}
    # Only the owner lists and decides.
    assert _get(client, tenant, driver_token, PATH).status_code == 403
    pending = _get(client, tenant, token, f"{PATH}").json()["reports"]
    assert [row["id"] for row in pending] == [report["id"]]
    confirmed = _post(client, tenant, token, f"{PATH}/{report['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED"
    assert confirmed.json()["confirmed_purchase_id"]
    # Confirming again changes nothing: one purchase, one payable, the list line advanced once.
    again = _post(client, tenant, token, f"{PATH}/{report['id']}/confirm")
    assert again.json()["confirmed_purchase_id"] == confirmed.json()["confirmed_purchase_id"]
    assert _count(session_factory, SupplierPurchase, tenant) == 1
    assert _balance(client, tenant, token, item["supplier_id"]) == {"USD": "30.0000"}
    with session_factory() as db:
        row = db.get(ProcurementItem, UUID(item["id"]))
        assert row is not None and row.purchased_quantity == 4
        actions = {
            event.action
            for event in db.query(AuditEvent).filter(AuditEvent.tenant_id == UUID(tenant))
        }
        assert {"PICKUP_REPORTED", "PICKUP_CONFIRMED"} <= actions
    rejected_after = _post(
        client, tenant, token, f"{PATH}/{report['id']}/reject", {"reason": "late"}
    )
    assert rejected_after.status_code == 409


def test_reject_with_reason_and_isolation(client, session_factory):
    tenant, token, driver_token, list_id, item = _assigned_list(client, session_factory, "pick2")
    report = _post(client, tenant, driver_token, PATH, _report(item, list_id)).json()
    assert (
        _post(client, tenant, token, f"{PATH}/{report['id']}/reject", {"reason": ""}).status_code
        == 422
    )
    rejected = _post(
        client, tenant, token, f"{PATH}/{report['id']}/reject", {"reason": "Wrong supplier"}
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    assert rejected.json()["reason"] == "Wrong supplier"
    assert _post(client, tenant, token, f"{PATH}/{report['id']}/confirm").status_code == 409
    assert _count(session_factory, SupplierPurchase, tenant) == 0
    assert _get(client, tenant, token, f"{PATH}").json()["reports"][0]["status"] == "REJECTED"
    only_pending = client.get(
        f"{PATH}?tenant_id={tenant}&status=PENDING", headers=_auth(token)
    ).json()
    assert only_pending["reports"] == []

    # A line from another supplier or list is refused; a list not assigned to the runner too.
    bad = _report(item, list_id)
    bad["lines"][0]["procurement_item_id"] = str(uuid4())
    assert _post(client, tenant, driver_token, PATH, bad).status_code == 422
    other_tenant, other_token, _d, other_list, other_item = _assigned_list(
        client, session_factory, "pick3"
    )
    assert _post(
        client, tenant, driver_token, PATH, _report(other_item, other_list)
    ).status_code in {
        403,
        404,
    }
    assert _count(session_factory, PickupReport, other_tenant) == 0
    assert _get(client, other_tenant, other_token, PATH).json()["reports"] == []
