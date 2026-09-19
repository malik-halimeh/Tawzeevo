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
    assert "performed_by" not in done.json()  # a driver gets the least-privilege projection
    owner_view = _get(client, tenant, token, f"/api/v1/delivery-tasks/{task['id']}").json()
    assert owner_view["performed_by"]["membership_id"] == other_membership

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


def test_driver_my_work_is_assigned_only_and_price_free(client, session_factory):
    """PHASE_07.md D: the driver sees assigned tasks with contact, items and the amount to
    collect — never costs, other tasks, suppliers or owner screens."""
    import re

    owner, tenant, token = _owner_context(client, session_factory, "p7work")
    _category, product, customer = _catalog(client, tenant, token, name="Olive Oil")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    first = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    second = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "4")
    _d1, driver_token, driver_membership = _driver(
        client, session_factory, tenant, "driver-p7w@example.com"
    )
    _d2, other_token, other_membership = _driver(
        client, session_factory, tenant, "driver-p7x@example.com"
    )
    mine = _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": first["id"], "assigned_membership_id": driver_membership},
    ).json()
    _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": second["id"], "assigned_membership_id": other_membership},
    )

    work = _get(client, tenant, driver_token, "/api/v1/delivery-tasks/my-work")
    assert work.status_code == 200, work.text
    body = work.json()
    assert body["role"] == "driver" and [t["id"] for t in body["tasks"]] == [mine["id"]]
    task = body["tasks"][0]
    assert task["customer_phone"] and task["items"][0]["quantity"] == "2.0000"
    assert task["amount_to_collect"] == first["net_sales"]
    assert not re.search(r"cost|margin|profit|supplier|assignee|customer_id", work.text, re.I)

    # The owner's own My Work is empty (nothing assigned to the owner) and never breaks.
    assert _get(client, tenant, token, "/api/v1/delivery-tasks/my-work").json()["tasks"] == []

    # Driver completes their task and gets the least-privilege projection back; the other
    # driver's task is out of reach; supplier and owner screens are denied.
    done = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{mine['id']}/complete",
        {"expected_version": 1, "note": "paid cash"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED" and "performed_by" not in done.json()
    other_task = _get(client, tenant, token, "/api/v1/delivery-tasks").json()["tasks"]
    other_id = next(t["id"] for t in other_task if t["id"] != mine["id"])
    stolen = _post(
        client,
        tenant,
        driver_token,
        f"/api/v1/delivery-tasks/{other_id}/complete",
        {"expected_version": 1},
    )
    assert stolen.status_code == 403
    for path in (
        "/api/v1/suppliers",
        "/api/v1/procurement/lists",
        f"/api/v1/supplier-prices/products/{product['id']}",
        "/api/v1/customer-ledger/debts",
    ):
        assert _get(client, tenant, driver_token, path).status_code == 403, path


def test_driver_sync_is_scoped_and_offline_completion_applies_once(client, session_factory):
    """PHASE_07.md I: driver device bootstraps without the owner projection, pulls only its own
    tasks, and may push only completions — each applied exactly once."""
    from uuid import uuid4 as _uuid4

    from test_sync_bootstrap import _bootstrap
    from test_sync_push import _op, _push

    owner, tenant, token = _owner_context(client, session_factory, "p7sync")
    _category, product, customer = _catalog(client, tenant, token, name="Bread")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    first = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    second = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    _d1, driver_token, driver_membership = _driver(
        client, session_factory, tenant, "driver-p7s@example.com"
    )
    _d2, _other_token, other_membership = _driver(
        client, session_factory, tenant, "driver-p7t@example.com"
    )
    mine = _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": first["id"], "assigned_membership_id": driver_membership},
    ).json()
    _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": second["id"], "assigned_membership_id": other_membership},
    )

    device = str(_uuid4())
    booted = _bootstrap(client, tenant, driver_token, device)
    assert booted.status_code == 200, booted.text
    assert booted.json()["collections"] == []  # no owner projection for a driver device
    pulled = client.get(
        f"/api/v1/sync/pull?tenant_id={tenant}&cursor=0&device_installation_id={device}",
        headers=_auth(driver_token),
    )
    assert pulled.status_code == 200, pulled.text
    changes = pulled.json()["changes"]
    assert {c["entity_type"] for c in changes} == {"delivery_task"}
    assert {c["payload"]["assigned_membership_id"] for c in changes} == {driver_membership}
    assert not any("unit_cost" in c["payload"] for c in changes)

    # Only completions may be pushed by a driver.
    forbidden = _push(
        client,
        tenant,
        driver_token,
        device,
        [_op("customer", "create", str(_uuid4()), {"name": "X", "phone": "+96170000009"})],
    )
    assert forbidden.status_code == 403
    complete = _op("delivery_task", "complete", mine["id"], {"note": "door"}, expected_version=1)
    applied = _push(client, tenant, driver_token, device, [complete]).json()["results"][0]
    assert applied["status"] == "applied", applied
    assert applied["projection"]["status"] == "COMPLETED"
    replay = _push(client, tenant, driver_token, device, [complete]).json()["results"][0]
    assert replay["replayed"] is True and replay["status"] == "applied"
    again = _op("delivery_task", "complete", mine["id"], {"note": "twice"}, expected_version=2)
    assert (
        _push(client, tenant, driver_token, device, [again]).json()["results"][0]["status"]
        == "rejected"
    )
    other_id = next(
        t["id"]
        for t in _get(client, tenant, token, "/api/v1/delivery-tasks").json()["tasks"]
        if t["id"] != mine["id"]
    )
    stolen = _op("delivery_task", "complete", other_id, {}, expected_version=1)
    assert (
        _push(client, tenant, driver_token, device, [stolen]).json()["results"][0]["status"]
        == "rejected"
    )
    with session_factory() as db:
        row = db.get(DeliveryTask, UUID(mine["id"]))
        assert row is not None and row.status == "COMPLETED" and row.version == 2
        assert str(row.performed_by_membership_id) == driver_membership


def test_owner_team_api_adds_registered_driver_and_revocation_locks_access(client, session_factory):
    """PHASE_07.md A/I: one membership one role; a revoked driver is refused on the next call."""
    from test_sync_bootstrap import _bootstrap

    owner, tenant, token = _owner_context(client, session_factory, "p7team")
    driver = _user(session_factory, "driver-p7team@example.com", SystemUserType.CLIENT)
    unknown = _post(
        client,
        tenant,
        token,
        f"/api/v1/tenants/{tenant}/memberships",
        {"email": "nobody-p7@example.com"},
    )
    assert unknown.status_code == 404
    added = _post(
        client, tenant, token, f"/api/v1/tenants/{tenant}/memberships", {"email": driver.email}
    )
    assert added.status_code == 201, added.text
    assert added.json()["role"] == "driver" and added.json()["is_self"] is False
    twice = _post(
        client, tenant, token, f"/api/v1/tenants/{tenant}/memberships", {"email": driver.email}
    )
    assert twice.status_code == 409
    driver_token = _login(client, driver.email)
    assert _get(client, tenant, driver_token, "/api/v1/delivery-tasks/my-work").status_code == 200
    device = str(uuid4())
    assert _bootstrap(client, tenant, driver_token, device).status_code == 200
    # Drivers cannot manage the team; owners cannot revoke themselves; revocation locks out.
    assert (
        _get(client, tenant, driver_token, f"/api/v1/tenants/{tenant}/memberships").status_code
        == 403
    )
    members = _get(client, tenant, token, f"/api/v1/tenants/{tenant}/memberships").json()["members"]
    me = next(m for m in members if m["is_self"])
    assert (
        _post(
            client, tenant, token, f"/api/v1/tenants/{tenant}/memberships/{me['id']}/revoke"
        ).status_code
        == 409
    )
    revoked = _post(
        client, tenant, token, f"/api/v1/tenants/{tenant}/memberships/{added.json()['id']}/revoke"
    )
    assert revoked.status_code == 200 and revoked.json()["is_active"] is False
    assert _get(client, tenant, driver_token, "/api/v1/delivery-tasks/my-work").status_code == 403
    pull = client.get(
        f"/api/v1/sync/pull?tenant_id={tenant}&cursor=0&device_installation_id={device}",
        headers=_auth(driver_token),
    )
    assert pull.status_code == 403
