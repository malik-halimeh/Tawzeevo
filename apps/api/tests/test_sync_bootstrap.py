"""P4-M1: device registry, authorized bootstrap, change log and versions (PHASE_04.md C/F/G)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from test_invoice_editor import _auth, _catalog, _owner_context

from tawzeevo_api.models import Customer, SyncChange, SyncDevice


def _bootstrap(client, tenant, token, device=None, **overrides):
    payload = {
        "device_installation_id": device or str(uuid4()),
        "protocol_version": 1,
        "app_schema_version": 1,
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/sync/bootstrap?tenant_id={tenant}", headers=_auth(token), json=payload
    )


def _page(client, tenant, token, device, collection, cursor=None, page_size=None):
    params = {"tenant_id": tenant, "device_installation_id": device}
    if cursor:
        params["cursor"] = cursor
    if page_size:
        params["page_size"] = page_size
    return client.get(f"/api/v1/sync/bootstrap/{collection}", headers=_auth(token), params=params)


def test_owner_bootstrap_registers_device_and_pages_the_authorized_snapshot(
    client, session_factory
):
    _owner, tenant, token = _owner_context(client, session_factory, "sync-boot")
    _category, product, customer = _catalog(client, tenant, token)
    for index in range(3):
        extra = client.post(
            f"/api/v1/tenants/{tenant}/customers",
            headers=_auth(token),
            json={"name": f"Extra {index}", "phone": f"+9617012345{index}"},
        )
        assert extra.status_code == 201, extra.text
    device = str(uuid4())

    started = _bootstrap(client, tenant, token, device)
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["protocol_version"] == 1 and body["page_size"] == 500
    assert body["device"]["device_installation_id"] == device
    assert body["device"]["revoked_at"] is None
    assert body["high_water_change_seq"] > 0, "catalog/customer creation produced change records"
    assert "customers" in body["collections"] and "invoices" in body["collections"]

    # Paginated, resumable snapshot ordered by id: 4 customers over pages of 3.
    first = _page(client, tenant, token, device, "customers", page_size=3)
    assert first.status_code == 200, first.text
    assert len(first.json()["items"]) == 3 and first.json()["next_cursor"]
    second = _page(
        client, tenant, token, device, "customers", cursor=first.json()["next_cursor"], page_size=3
    )
    assert second.status_code == 200, second.text
    assert len(second.json()["items"]) == 1 and second.json()["next_cursor"] is None
    ids = {row["id"] for row in first.json()["items"] + second.json()["items"]}
    assert customer["id"] in ids and len(ids) == 4
    assert all(row["version"] == 1 for row in first.json()["items"])

    products = _page(client, tenant, token, device, "tenant_products").json()["items"]
    assert [row["id"] for row in products] == [product["id"]]
    assert "unit_price" in products[0] and "version" in products[0]
    barcodes = _page(client, tenant, token, device, "tenant_barcodes").json()["items"]
    assert barcodes and barcodes[0]["tenant_product_id"] == product["id"]

    # Re-bootstrapping the same installation refreshes the same device row.
    again = _bootstrap(client, tenant, token, device)
    assert again.status_code == 200 and again.json()["device"]["id"] == body["device"]["id"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(SyncDevice)) == 1


def test_device_id_is_never_authorization_and_snapshot_is_tenant_scoped(client, session_factory):
    _, tenant_a, token_a = _owner_context(client, session_factory, "sync-a")
    _, tenant_b, token_b = _owner_context(client, session_factory, "sync-b")
    _catalog(client, tenant_a, token_a)
    _catalog(client, tenant_b, token_b, barcode="5280000000029")
    device = str(uuid4())
    assert _bootstrap(client, tenant_a, token_a, device).status_code == 200

    # No session: denied regardless of the device id.
    anonymous = client.get(
        "/api/v1/sync/bootstrap/customers",
        params={"tenant_id": tenant_a, "device_installation_id": device},
    )
    assert anonymous.status_code == 401
    # Another tenant's owner with the registered device id: not their tenant.
    foreign = _page(client, tenant_a, token_b, device, "customers")
    assert foreign.status_code == 403, foreign.text
    # Same owner, device registered for tenant A only: tenant B needs its own bootstrap.
    unregistered = _page(client, tenant_b, token_b, device, "customers")
    assert unregistered.status_code == 404
    assert unregistered.json()["detail"]["code"] == "SYNC_DEVICE_NOT_REGISTERED"
    # Tenant B snapshot never contains tenant A rows.
    assert _bootstrap(client, tenant_b, token_b, device).status_code == 200
    rows = _page(client, tenant_b, token_b, device, "customers").json()["items"]
    assert {row["tenant_id"] for row in rows} == {tenant_b}


def test_protocol_mismatch_is_rejected_and_driver_cannot_bootstrap(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "sync-proto")
    old = _bootstrap(client, tenant, token, protocol_version=99)
    assert old.status_code == 409 and old.json()["detail"]["code"] == "SYNC_PROTOCOL_MISMATCH"
    newer = _bootstrap(client, tenant, token, app_schema_version=99)
    assert newer.status_code == 409 and newer.json()["detail"]["code"] == "SYNC_SCHEMA_TOO_NEW"


def test_mutations_append_ordered_change_records_and_bump_versions(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "sync-changes")
    _category, product, customer = _catalog(client, tenant, token)
    with session_factory() as db:
        before = int(
            db.scalar(
                select(func.coalesce(func.max(SyncChange.change_seq), 0)).where(
                    SyncChange.tenant_id == UUID(tenant)
                )
            )
            or 0
        )
    updated = client.put(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}",
        headers=_auth(token),
        json={"address": "Hamra, Beirut"},
    )
    assert updated.status_code == 200, updated.text
    with session_factory() as db:
        row = db.get(Customer, UUID(customer["id"]))
        assert row is not None and row.version == 2
        changes = list(
            db.scalars(
                select(SyncChange)
                .where(SyncChange.tenant_id == UUID(tenant), SyncChange.change_seq > before)
                .order_by(SyncChange.change_seq)
            )
        )
        assert [c.entity_type for c in changes] == ["customer"]
        assert changes[0].operation == "upsert" and changes[0].version == 2
        assert changes[0].payload["address"] == "Hamra, Beirut"
        assert changes[0].payload["version"] == 2
        # Every tracked insert from the catalog helper produced a change with a stable sequence.
        types = set(
            db.scalars(select(SyncChange.entity_type).where(SyncChange.tenant_id == UUID(tenant)))
        )
        assert {"customer", "category", "tenant_product", "tenant_barcode"} <= types
        seqs = list(
            db.scalars(
                select(SyncChange.change_seq)
                .where(SyncChange.tenant_id == UUID(tenant))
                .order_by(SyncChange.change_seq)
            )
        )
        assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))


def test_forced_rls_hides_other_tenant_sync_rows(client, session_factory, test_engine):
    _, tenant, token = _owner_context(client, session_factory, "sync-rls")
    _catalog(client, tenant, token)
    assert _bootstrap(client, tenant, token).status_code == 200
    role = f"tawzeevo_sync_test_{uuid4().hex}"
    with test_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        connection.exec_driver_sql(f'GRANT SELECT ON sync_devices, sync_changes TO "{role}"')
    try:
        with test_engine.connect() as connection:
            connection.exec_driver_sql(f'SET ROLE "{role}"')
            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": tenant}
            )
            assert len(list(connection.execute(select(SyncDevice.id)))) == 1
            assert len(list(connection.execute(select(SyncChange.change_seq)))) > 0
            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :id, true)"), {"id": str(uuid4())}
            )
            assert list(connection.execute(select(SyncDevice.id))) == []
            assert list(connection.execute(select(SyncChange.change_seq))) == []
    finally:
        with test_engine.begin() as connection:
            connection.exec_driver_sql(f'REVOKE ALL ON sync_devices, sync_changes FROM "{role}"')
            connection.exec_driver_sql(f'DROP ROLE "{role}"')


def test_retired_device_must_rebootstrap(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "sync-retire")
    device = str(uuid4())
    assert _bootstrap(client, tenant, token, device).status_code == 200
    with session_factory() as db:
        row = db.scalar(select(SyncDevice).where(SyncDevice.device_installation_id == UUID(device)))
        assert row is not None
        row.last_seen_at = datetime.now(UTC) - timedelta(days=91)
        db.commit()
    stale = _page(client, tenant, token, device, "customers")
    assert stale.status_code == 410
    assert stale.json()["detail"]["code"] == "SYNC_REBOOTSTRAP_REQUIRED"
    assert _bootstrap(client, tenant, token, device).status_code == 200
    assert _page(client, tenant, token, device, "customers").status_code == 200
