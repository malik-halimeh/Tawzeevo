"""D-114: a driver's collection report is not a payment until the owner confirms it; the customer
sees the recorded payment on their own storefront notifications."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_customer_access import HEADER, _issue
from test_delivery_tasks import _driver, _post
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice

from tawzeevo_api.models import CollectionReport, CustomerNotification, Payment

REPORTS = "/api/v1/collection-reports"


def _setup(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Bread")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    invoice = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    _user, driver_token, membership = _driver(
        client, session_factory, tenant, f"driver-{suffix}@example.com"
    )
    task = _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": invoice["id"], "assigned_membership_id": membership},
    ).json()
    return tenant, token, driver_token, customer, invoice, task


def _task(client, tenant, token, task_id):
    return client.get(
        f"/api/v1/delivery-tasks/{task_id}?tenant_id={tenant}", headers=_auth(token)
    ).json()


def test_partial_collection_waits_for_the_owner_then_becomes_a_receipt(client, session_factory):
    tenant, token, driver_token, customer, invoice, task = _setup(client, session_factory, "col1")
    owed = Decimal(task["amount_to_collect"])
    assert owed > 0
    too_much = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 1, "collection": {"kind": "PARTIAL", "amount": str(owed + 1)}},
    )
    assert too_much.status_code == 422, too_much.text
    assert _task(client, tenant, token, task["id"])["status"] == "ASSIGNED"  # nothing half-done
    missing = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 1, "collection": {"kind": "PARTIAL"}},
    )
    assert missing.status_code == 422
    done = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 1, "collection": {"kind": "PARTIAL", "amount": "5"}},
    )
    assert done.status_code == 200, done.text

    # Not a payment yet: the amount owed is unchanged and no payment exists.
    assert Decimal(_task(client, tenant, token, task["id"])["amount_to_collect"]) == owed
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
    assert (
        client.get(f"{REPORTS}?tenant_id={tenant}", headers=_auth(driver_token)).status_code == 403
    )
    pending = client.get(
        f"{REPORTS}?tenant_id={tenant}&status=PENDING", headers=_auth(token)
    ).json()["reports"]
    assert len(pending) == 1
    report = pending[0]
    assert (report["kind"], report["amount"], report["currency"]) == ("PARTIAL", "5.0000", "USD")
    assert report["official_invoice_number"] == invoice["official_invoice_number"]

    confirmed = _post(client, tenant, token, f"{REPORTS}/{report['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "CONFIRMED" and confirmed.json()["confirmed_payment_id"]
    again = _post(client, tenant, token, f"{REPORTS}/{report['id']}/confirm")
    assert again.json()["confirmed_payment_id"] == confirmed.json()["confirmed_payment_id"]
    obligations = client.get(
        f"/api/v1/payments/customers/{customer['id']}/obligations?tenant_id={tenant}&currency=USD",
        headers=_auth(token),
    ).json()["obligations"]
    row = next(item for item in obligations if item["source_id"] == invoice["id"])
    assert Decimal(row["outstanding_amount"]) == owed - 5  # allocated to that invoice
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
    assert (
        _post(
            client, tenant, token, f"{REPORTS}/{report['id']}/reject", {"reason": "late"}
        ).status_code
        == 409
    )

    # The customer sees it on their own storefront, and only there.
    _link, secret = _issue(client, tenant, token, customer["id"])
    listed = client.get("/api/v1/public/notifications", headers={HEADER: secret})
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["unread"] == 1
    assert body["notifications"][0]["kind"] == "PAYMENT_RECORDED"
    assert body["notifications"][0]["data"] == {
        "amount": "5.0000",
        "currency": "USD",
        "invoice_number": invoice["official_invoice_number"],
    }
    assert (
        client.post("/api/v1/public/notifications/read", headers={HEADER: secret}).status_code
        == 204
    )
    assert (
        client.get("/api/v1/public/notifications", headers={HEADER: secret}).json()["unread"] == 0
    )
    assert client.get("/api/v1/public/notifications").status_code == 404
    assert (
        client.get(
            "/api/v1/public/notifications", headers={HEADER: "0" * 32 + "." + "A" * 43}
        ).status_code
        == 404
    )


def test_full_none_and_reject_and_offline_exactly_once(client, session_factory):
    from test_sync_bootstrap import _bootstrap
    from test_sync_push import _op, _push

    tenant, token, driver_token, _customer, _invoice, task = _setup(client, session_factory, "col2")
    # "Not paid": acknowledged by the owner, nothing recorded as money.
    none = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 1, "collection": {"kind": "NONE"}},
    )
    assert none.status_code == 200, none.text
    report = client.get(f"{REPORTS}?tenant_id={tenant}", headers=_auth(token)).json()["reports"][0]
    assert report["kind"] == "NONE" and report["amount"] is None
    acknowledged = _post(client, tenant, token, f"{REPORTS}/{report['id']}/confirm").json()
    assert acknowledged["status"] == "CONFIRMED" and acknowledged["confirmed_payment_id"] is None

    # Offline: "Paid in full" rides the completion push; a replay makes no second report.
    tenant2, token2, driver2, _c2, _i2, task2 = _setup(client, session_factory, "col3")
    device = str(uuid4())
    assert _bootstrap(client, tenant2, driver2, device).status_code == 200
    op = _op(
        "delivery_task",
        "complete",
        task2["id"],
        {"note": None, "collection": {"kind": "FULL"}},
        expected_version=1,
    )
    first = _push(client, tenant2, driver2, device, [op]).json()["results"][0]
    assert first["status"] == "applied", first
    replay = _push(client, tenant2, driver2, device, [op]).json()["results"][0]
    assert replay["replayed"] is True
    with session_factory() as db:
        rows = list(
            db.scalars(select(CollectionReport).where(CollectionReport.tenant_id == UUID(tenant2)))
        )
    assert len(rows) == 1 and rows[0].kind == "FULL"
    assert rows[0].amount == Decimal(task2["amount_to_collect"])
    assert str(rows[0].idempotency_key) == op["operation_id"]
    rejected = _post(
        client, tenant2, token2, f"{REPORTS}/{rows[0].id}/reject", {"reason": "Not received"}
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CustomerNotification)) == 0
    # Another business sees none of these reports.
    assert (
        client.get(f"{REPORTS}?tenant_id={tenant}", headers=_auth(token)).json()["reports"][0]["id"]
        == report["id"]
    )
    assert (
        len(client.get(f"{REPORTS}?tenant_id={tenant2}", headers=_auth(token2)).json()["reports"])
        == 1
    )
