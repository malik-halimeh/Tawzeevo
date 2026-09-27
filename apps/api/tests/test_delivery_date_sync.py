"""D-104: an order's delivery date and its open delivery's date stay equal, both ways."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from test_invoice_editor import _auth, _catalog, _owner_context
from test_order_review import _order, _place
from test_storefront import _publish

from tawzeevo_api.models import AuditEvent, DeliveryReminder, Invoice


def _confirmed_order(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    placed, _reference = _place(
        client, session_factory, owner, tenant, token, product, phone=customer["phone"]
    )
    order_id = placed["order_id"]
    linked = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/link-customer",
        headers=_auth(token),
        json={"customer_id": customer["id"]},
    )
    assert linked.status_code == 200, linked.text
    with session_factory() as db:
        invoice = db.scalar(select(Invoice).where(Invoice.tenant_id == UUID(tenant)))
        assert invoice is not None
        invoice_id, revision_id = str(invoice.id), str(invoice.current_revision_id)
    confirmed = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/confirm",
        headers=_auth(token),
        json={"expected_revision_id": revision_id},
    )
    assert confirmed.status_code == 200, confirmed.text
    return tenant, token, order_id, invoice_id


def test_order_date_and_delivery_date_follow_each_other(client, session_factory):
    tenant, token, order_id, invoice_id = _confirmed_order(client, session_factory, "datesync")
    day = (datetime.now(UTC) + timedelta(days=3)).date()
    created = client.post(
        "/api/v1/delivery-tasks",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={"invoice_id": invoice_id, "assigned_membership_id": None, "delivery_date": None},
    )
    assert created.status_code == 201, created.text
    task = created.json()

    # The order's date changes: the open delivery takes it, with a version bump and an audit entry.
    dated = client.put(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": day.isoformat()},
    )
    assert dated.status_code == 200, dated.text
    after_order = client.get(
        f"/api/v1/delivery-tasks/{task['id']}", params={"tenant_id": tenant}, headers=_auth(token)
    ).json()
    assert after_order["delivery_date"] == day.isoformat()
    assert after_order["version"] == task["version"] + 1

    # The delivery's date changes: the order and its reminder take it.
    later = day + timedelta(days=2)
    patched = client.patch(
        f"/api/v1/delivery-tasks/{task['id']}",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={"expected_version": after_order["version"], "delivery_date": later.isoformat()},
    )
    assert patched.status_code == 200, patched.text
    assert _order(client, tenant, token, order_id)["order"]["delivery_date"] == later.isoformat()
    with session_factory() as db:
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.tenant_id == UUID(tenant))
        )
        assert reminder is not None and reminder.delivery_date == later
        assert reminder.status == "SCHEDULED"
        sources = {
            event.details.get("source")
            for event in db.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == UUID(tenant),
                    AuditEvent.action.in_(["ORDER_DELIVERY_DATE_SET", "delivery_task_updated"]),
                )
            )
        }
        assert f"order:{order_id}" in sources and f"delivery_task:{task['id']}" in sources

    # Clearing the delivery's date clears the order's and cancels its reminder.
    cleared = client.patch(
        f"/api/v1/delivery-tasks/{task['id']}",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={"expected_version": patched.json()["version"], "delivery_date": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert _order(client, tenant, token, order_id)["order"]["delivery_date"] is None
    with session_factory() as db:
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.tenant_id == UUID(tenant))
        )
        assert reminder is not None and reminder.status == "CANCELLED"

    # A finished delivery is left as it was when the order's date changes again.
    done = client.post(
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={"expected_version": cleared.json()["version"], "note": None},
    )
    assert done.status_code == 200, done.text
    client.put(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": day.isoformat()},
    )
    final = client.get(
        f"/api/v1/delivery-tasks/{task['id']}", params={"tenant_id": tenant}, headers=_auth(token)
    ).json()
    assert final["delivery_date"] is None and final["version"] == done.json()["version"]
