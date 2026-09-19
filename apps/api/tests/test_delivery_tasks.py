"""Phase 7 P7-M1: delivery tasks, owner-as-operator default, neutral assignee authorization,
D-063 lifecycle, cancellation integration (PHASE_07.md A/B/C)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
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

from tawzeevo_api.models import (
    AuditEvent,
    DeliveryTask,
    SystemUserType,
    TenantMembership,
    TenantRole,
)


def _post(client, tenant, token, path, json=None):
    return client.post(f"{path}?tenant_id={tenant}", headers=_auth(token), json=json)


def _get(client, tenant, token, path):
    return client.get(f"{path}?tenant_id={tenant}", headers=_auth(token))


def _driver(client, session_factory, tenant, email):
    user = _user(session_factory, email, SystemUserType.CLIENT)
    with session_factory() as db:
        membership = TenantMembership(
            tenant_id=UUID(tenant), user_id=user.id, role=TenantRole.DRIVER, is_active=True
        )
        db.add(membership)
        db.commit()
        membership_id = membership.id
    return user, _login(client, email), str(membership_id)


def test_sole_owner_is_the_default_operator_and_completes_own_task(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p7sole")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    draft = _post(
        client,
        tenant,
        token,
        "/api/v1/invoices",
        _confirmable_payload(customer["id"], product["id"]),
    ).json()

    # A draft is not eligible; a confirmed invoice is.
    refused = _post(client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": draft["id"]})
    assert (
        refused.status_code == 409 and refused.json()["detail"]["code"] == "INVOICE_NOT_CONFIRMED"
    )
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "3")
    eligible = _get(client, tenant, token, "/api/v1/delivery-tasks/eligible-invoices").json()
    assert [row["invoice_id"] for row in eligible["invoices"]] == [confirmed["id"]]

    # No assignee given: the sole owner is the operator; no driver setup is required.
    created = _post(
        client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": confirmed["id"]}
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["status"] == "ASSIGNED" and task["assignee"]["role"] == "owner"
    assert task["assignee"]["is_self"] is True
    assert task["customer_name"] and task["items"][0]["product_name"] == "Cedar Water"
    assert task["amount_to_collect"] == confirmed["net_sales"]
    listing = _get(client, tenant, token, "/api/v1/delivery-tasks").json()
    assert listing["sole_operator"] is True and len(listing["eligible_members"]) == 1
    assert _get(client, tenant, token, "/api/v1/delivery-tasks/eligible-invoices").json() == {
        "invoices": []
    }
    duplicate = _post(
        client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": confirmed["id"]}
    )
    assert (
        duplicate.status_code == 409
        and duplicate.json()["detail"]["code"] == "DELIVERY_TASK_EXISTS"
    )

    # Owner completes with the version; the performer is recorded; terminal afterwards (D-063).
    stale = _post(
        client,
        tenant,
        token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 9},
    )
    assert stale.status_code == 409
    done = _post(
        client,
        tenant,
        token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": task["version"], "note": "left at the counter"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED" and done.json()["performed_by"]["is_self"] is True
    again = _post(
        client,
        tenant,
        token,
        f"/api/v1/delivery-tasks/{task['id']}/cancel",
        {"expected_version": done.json()["version"], "reason": "oops"},
    )
    assert again.status_code == 409 and again.json()["detail"]["code"] == "DELIVERY_TASK_CLOSED"
    # A mistaken completion is followed by a new task for the same invoice, never a reopen.
    second = _post(client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": confirmed["id"]})
    assert second.status_code == 201
    with session_factory() as db:
        assert (
            db.scalar(
                select(AuditEvent).where(
                    AuditEvent.action == "delivery_task_created",
                    AuditEvent.tenant_id == UUID(tenant),
                )
            )
            is not None
        )
        assert (
            len(
                db.scalars(select(DeliveryTask).where(DeliveryTask.tenant_id == UUID(tenant))).all()
            )
            == 2
        )


def test_assignment_is_owner_only_audited_and_protected(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p7assign")
    _category, product, customer = _catalog(client, tenant, token, name="Labneh")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    _d1, driver_token, driver_membership = _driver(
        client, session_factory, tenant, "driver-p7a@example.com"
    )
    _d2, other_driver_token, other_membership = _driver(
        client, session_factory, tenant, "driver-p7b@example.com"
    )

    # Several eligible members: the owner must choose.
    ambiguous = _post(
        client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": confirmed["id"]}
    )
    assert (
        ambiguous.status_code == 422 and ambiguous.json()["detail"]["code"] == "ASSIGNEE_REQUIRED"
    )
    listing = _get(client, tenant, token, "/api/v1/delivery-tasks").json()
    assert listing["sole_operator"] is False and len(listing["eligible_members"]) == 3
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": confirmed["id"], "assigned_membership_id": driver_membership},
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["assignee"]["role"] == "driver" and task["assignee"]["is_self"] is False

    # Driver cannot assign, reassign, cancel or list owner views; owner reassigns with audit.
    for path, method, body in (
        (
            f"/api/v1/delivery-tasks/{task['id']}/assignee",
            "put",
            {"assigned_membership_id": other_membership, "expected_version": 1},
        ),
        (
            f"/api/v1/delivery-tasks/{task['id']}/cancel",
            "post",
            {"expected_version": 1, "reason": "x"},
        ),
        ("/api/v1/delivery-tasks", "get", None),
        ("/api/v1/delivery-tasks/eligible-invoices", "get", None),
    ):
        response = (
            getattr(client, method)(
                f"{path}?tenant_id={tenant}", headers=_auth(driver_token), json=body
            )
            if body
            else client.get(f"{path}?tenant_id={tenant}", headers=_auth(driver_token))
        )
        assert response.status_code == 403, (path, response.text)
    inactive = client.put(
        f"/api/v1/delivery-tasks/{task['id']}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"assigned_membership_id": str(uuid4()), "expected_version": 1},
    )
    assert inactive.status_code == 404
    reassigned = client.put(
        f"/api/v1/delivery-tasks/{task['id']}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"assigned_membership_id": other_membership, "expected_version": 1},
    )
    assert reassigned.status_code == 200 and reassigned.json()["version"] == 2
    with session_factory() as db:
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "delivery_task_reassigned"))
        assert audit is not None and audit.details["previous"] == driver_membership

    # The previously assigned driver can no longer complete; the assigned one can.
    old = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 2},
    )
    assert old.status_code == 403 and old.json()["detail"]["code"] == "DELIVERY_TASK_NOT_ASSIGNED"
    done = _post(
        client,
        tenant,
        other_driver_token,
        f"/api/v1/delivery-tasks/{task['id']}/complete",
        {"expected_version": 2},
    )
    assert done.status_code == 200, done.text
    assert done.json()["performed_by"]["membership_id"] == other_membership

    # Cross-tenant: another business sees nothing.
    _o, other_tenant, other_token = _owner_context(client, session_factory, "p7assign2")
    assert (
        _get(client, other_tenant, other_token, f"/api/v1/delivery-tasks/{task['id']}").status_code
        == 404
    )


def test_invoice_cancellation_closes_the_open_task(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p7cancel")
    _category, product, customer = _catalog(client, tenant, token, name="Jam")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    task = _post(
        client, tenant, token, "/api/v1/delivery-tasks", {"invoice_id": confirmed["id"]}
    ).json()
    cancelled = _post(
        client,
        tenant,
        token,
        f"/api/v1/invoices/{confirmed['id']}/cancel",
        {"idempotency_key": str(uuid4()), "reason": "customer refused"},
    )
    assert cancelled.status_code == 200, cancelled.text
    after = _get(client, tenant, token, f"/api/v1/delivery-tasks/{task['id']}").json()
    assert after["status"] == "CANCELLED" and after["cancel_reason"] == "invoice cancelled"
    # And a cancelled invoice is no longer eligible.
    assert _get(client, tenant, token, "/api/v1/delivery-tasks/eligible-invoices").json() == {
        "invoices": []
    }
