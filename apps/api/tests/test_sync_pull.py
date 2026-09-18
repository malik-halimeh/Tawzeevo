"""P4-M3: pull paging/ack, tombstones, retention floor, re-bootstrap and revocation."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from test_invoice_editor import PASSWORD, _auth, _catalog, _login, _owner_context
from test_sync_bootstrap import _bootstrap
from test_sync_push import _op, _push

from tawzeevo_api.models import (
    SyncChange,
    SyncDevice,
    Tenant,
    TenantBarcode,
    TenantMembership,
    User,
)
from tawzeevo_api.services.sync import purge_sync_changes


def _pull(client, tenant, token, device, cursor=0, page_size=None):
    params = {"tenant_id": tenant, "device_installation_id": device, "cursor": cursor}
    if page_size:
        params["page_size"] = page_size
    return client.get("/api/v1/sync/pull", headers=_auth(token), params=params)


def test_pull_pages_changes_in_order_and_acknowledges_the_cursor(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "pull-order")
    device = str(uuid4())
    started = _bootstrap(client, tenant, token, device).json()
    cursor = started["high_water_change_seq"]
    _category, product, customer = _catalog(client, tenant, token)
    for address in ("A", "B", "C"):
        assert (
            client.put(
                f"/api/v1/tenants/{tenant}/customers/{customer['id']}",
                headers=_auth(token),
                json={"address": address},
            ).status_code
            == 200
        )

    first = _pull(client, tenant, token, device, cursor=cursor, page_size=4)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["has_more"] is True and len(body["changes"]) == 4
    seqs = [row["change_seq"] for row in body["changes"]]
    assert seqs == sorted(seqs) and seqs[0] > cursor
    types = [row["entity_type"] for row in body["changes"]]
    assert "category" in types and "tenant_product" in types and "customer" in types

    second = _pull(client, tenant, token, device, cursor=body["next_cursor"], page_size=50).json()
    assert second["has_more"] is False
    versions = [row["version"] for row in second["changes"] if row["entity_id"] == customer["id"]]
    assert versions == sorted(versions) and versions[-1] == 4
    assert second["changes"][-1]["payload"]["address"] == "C"
    assert second["next_cursor"] == second["high_water_change_seq"]
    with session_factory() as db:
        row = db.scalar(select(SyncDevice).where(SyncDevice.device_installation_id == UUID(device)))
        assert row is not None and row.last_acknowledged_change_seq == body["next_cursor"]
    # A device's own pushed operation is attributed in the change it produced.
    op = _op("customer", "update", customer["id"], {"address": "D"}, expected_version=4)
    assert _push(client, tenant, token, device, [op]).json()["results"][0]["status"] == "applied"
    own = _pull(client, tenant, token, device, cursor=second["next_cursor"]).json()["changes"]
    assert own[-1]["operation_id"] == op["operation_id"]
    assert own[-1]["device_installation_id"] == device


def test_hard_deletes_become_tombstones_and_flow_through_pull(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "pull-tombstone")
    device = str(uuid4())
    cursor = _bootstrap(client, tenant, token, device).json()["high_water_change_seq"]
    _category, product, _customer = _catalog(client, tenant, token)
    with session_factory() as db:
        barcode = db.scalar(
            select(TenantBarcode).where(TenantBarcode.tenant_product_id == UUID(product["id"]))
        )
        assert barcode is not None
        barcode_id = barcode.id
        db.delete(barcode)
        db.commit()
    changes = _pull(client, tenant, token, device, cursor=cursor).json()["changes"]
    deletions = [row for row in changes if row["operation"] == "delete"]
    assert deletions and deletions[-1]["entity_type"] == "tenant_barcode"
    assert deletions[-1]["entity_id"] == str(barcode_id)
    assert deletions[-1]["payload"] == {"id": str(barcode_id)}


def test_purge_keeps_what_active_devices_need_and_forces_rebootstrap_below_the_floor(
    client, session_factory
):
    _, tenant, token = _owner_context(client, session_factory, "pull-purge")
    fresh = str(uuid4())
    stale = str(uuid4())
    cursor = _bootstrap(client, tenant, token, fresh).json()["high_water_change_seq"]
    assert _bootstrap(client, tenant, token, stale).status_code == 200
    _catalog(client, tenant, token)
    water = _pull(client, tenant, token, fresh, cursor=cursor).json()["high_water_change_seq"]
    assert _pull(client, tenant, token, fresh, cursor=water).status_code == 200  # ack everything
    with session_factory() as db:
        # Age every change past the retention window.
        for row in db.scalars(select(SyncChange).where(SyncChange.tenant_id == UUID(tenant))):
            row.occurred_at = datetime.now(UTC) - timedelta(days=120)
        db.commit()
        # The stale device has not acknowledged anything, so nothing may be purged yet (D-053).
        assert purge_sync_changes(db, UUID(tenant)) == 0
        # Retire the stale device: it no longer holds retention back.
        stale_row = db.scalar(
            select(SyncDevice).where(SyncDevice.device_installation_id == UUID(stale))
        )
        assert stale_row is not None
        stale_row.last_seen_at = datetime.now(UTC) - timedelta(days=100)
        db.commit()
        purged = purge_sync_changes(db, UUID(tenant))
        assert purged > 0
        floor = db.get(Tenant, UUID(tenant)).sync_retention_floor
        assert floor == water
    # The fresh device is at the floor and keeps syncing incrementally.
    assert _pull(client, tenant, token, fresh, cursor=water).status_code == 200
    # A device below the floor must re-bootstrap; the stale one is also retired by now.
    retired = _pull(client, tenant, token, stale, cursor=cursor)
    assert retired.status_code == 410
    assert retired.json()["detail"]["code"] == "SYNC_REBOOTSTRAP_REQUIRED"
    below = _pull(client, tenant, token, fresh, cursor=cursor)
    assert below.status_code == 410
    assert _bootstrap(client, tenant, token, stale).status_code == 200
    assert _pull(client, tenant, token, stale, cursor=water).status_code == 200


def test_membership_revocation_and_tenant_suspension_revoke_devices(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "pull-revoke")
    device = str(uuid4())
    assert _bootstrap(client, tenant, token, device).status_code == 200
    # A second owner so the first can be revoked without orphaning the tenant.
    with session_factory() as db:
        from tawzeevo_api.models import SystemUserType, TenantRole
        from tawzeevo_api.security import hash_password

        second = User(
            first_name="Second",
            last_name="Owner",
            email="owner2-pull-revoke@example.com",
            phone="+96170999001",
            city="Beirut",
            age=30,
            type=SystemUserType.CLIENT,
            password_hash=hash_password(PASSWORD),
        )
        db.add(second)
        db.flush()
        db.add(
            TenantMembership(
                tenant_id=UUID(tenant), user_id=second.id, role=TenantRole.OWNER, is_active=True
            )
        )
        db.commit()
        second_token = _login(client, second.email)
        first_membership = db.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == UUID(tenant), TenantMembership.user_id == owner.id
            )
        )
        assert first_membership is not None
        membership_id = first_membership.id
    revoked = client.post(
        f"/api/v1/tenants/{tenant}/memberships/{membership_id}/revoke", headers=_auth(second_token)
    )
    assert revoked.status_code in (200, 404), revoked.text
    with session_factory() as db:
        from tawzeevo_api.services.memberships import revoke_membership

        if revoked.status_code == 404:  # no HTTP management route: use the internal service
            revoke_membership(db, UUID(tenant), membership_id)
        row = db.scalar(select(SyncDevice).where(SyncDevice.device_installation_id == UUID(device)))
        assert row is not None and row.revoked_at is not None
        assert row.revoked_reason == "MEMBERSHIP_REVOKED"
    denied = _pull(client, tenant, token, device, cursor=0)
    assert denied.status_code == 403

    # Tenant suspension revokes the remaining owner's device server-side too.
    other_device = str(uuid4())
    assert _bootstrap(client, tenant, second_token, other_device).status_code == 200
    with session_factory() as db:
        from tawzeevo_api.schemas.platform import SuspendTenantRequest
        from tawzeevo_api.services.platform import suspend_tenant

        admin = db.scalar(select(User).where(User.type == SystemUserType.ADMIN))
        assert admin is not None
        suspend_tenant(
            db,
            UUID(tenant),
            admin,
            SuspendTenantRequest.model_validate({"reason": "ADMINISTRATIVE"}),
        )
        row = db.scalar(
            select(SyncDevice).where(SyncDevice.device_installation_id == UUID(other_device))
        )
        assert row is not None and row.revoked_reason == "TENANT_SUSPENDED"
    assert _pull(client, tenant, second_token, other_device, cursor=0).status_code == 403
