"""P4-M2: idempotent push, entity versions, conflict envelope, per-operation atomicity."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import _auth, _catalog, _owner_context
from test_sync_bootstrap import _bootstrap

from tawzeevo_api.models import Customer, SyncChange, SyncOperation


def _op(entity_type, operation_type, entity_id, payload, expected_version=None, operation_id=None):
    return {
        "operation_id": operation_id or str(uuid4()),
        "entity_type": entity_type,
        "operation_type": operation_type,
        "entity_id": entity_id,
        "expected_version": expected_version,
        "payload": payload,
        "client_timestamp": datetime.now(UTC).isoformat(),
    }


def _push(client, tenant, token, device, operations):
    return client.post(
        f"/api/v1/sync/push?tenant_id={tenant}",
        headers=_auth(token),
        json={"device_installation_id": device, "protocol_version": 1, "operations": operations},
    )


def _device(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    device = str(uuid4())
    assert _bootstrap(client, tenant, token, device).status_code == 200
    return owner, tenant, token, device


def test_create_and_update_apply_once_with_replay_and_change_records(client, session_factory):
    _, tenant, token, device = _device(client, session_factory, "push-basic")
    customer_id = str(uuid4())
    create = _op(
        "customer", "create", customer_id, {"name": "Offline Maya", "phone": "+96170123499"}
    )
    first = _push(client, tenant, token, device, [create])
    assert first.status_code == 200, first.text
    result = first.json()["results"][0]
    assert result["status"] == "applied" and result["replayed"] is False
    assert result["entity_id"] == customer_id and result["version"] == 1
    assert result["projection"]["phone"] == "+96170123499"

    replay = _push(client, tenant, token, device, [create]).json()["results"][0]
    assert replay["status"] == "applied" and replay["replayed"] is True
    assert replay["entity_id"] == customer_id
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Customer)
                .where(Customer.tenant_id == UUID(tenant), Customer.name == "Offline Maya")
            )
            == 1
        )
        change = db.scalar(
            select(SyncChange).where(
                SyncChange.tenant_id == UUID(tenant), SyncChange.entity_id == UUID(customer_id)
            )
        )
        assert change is not None
        assert str(change.operation_id) == create["operation_id"]
        assert str(change.device_installation_id) == device

    update = _op("customer", "update", customer_id, {"address": "Byblos"}, expected_version=1)
    applied = _push(client, tenant, token, device, [update]).json()["results"][0]
    assert applied["status"] == "applied" and applied["version"] == 2
    assert applied["projection"]["address"] == "Byblos"

    # Same operation id, different payload -> rejected, nothing changes.
    twisted = dict(create, payload={"name": "Someone Else", "phone": "+96170123499"})
    rejected = _push(client, tenant, token, device, [twisted]).json()["results"][0]
    assert rejected["status"] == "rejected"
    assert rejected["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_stale_expected_version_returns_conflict_envelope_without_overwriting(
    client, session_factory
):
    _, tenant, token, device = _device(client, session_factory, "push-conflict")
    _category, _product, customer = _catalog(client, tenant, token)
    # Server-side edit bumps the version to 2 while the device still believes 1.
    edited = client.put(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}",
        headers=_auth(token),
        json={"address": "Server address"},
    )
    assert edited.status_code == 200
    stale = _op(
        "customer", "update", customer["id"], {"address": "Device address"}, expected_version=1
    )
    response = _push(client, tenant, token, device, [stale]).json()["results"][0]
    assert response["status"] == "conflict"
    envelope = response["conflict"]
    assert envelope["server_version"] == 2 and envelope["client_expected_version"] == 1
    assert envelope["merge_strategy"] == "manual"
    assert envelope["server_projection"]["address"] == "Server address"
    assert envelope["request_id"]
    with session_factory() as db:
        row = db.get(Customer, UUID(customer["id"]))
        assert row is not None and row.address == "Server address" and row.version == 2
    # Replaying the stale command returns the recorded conflict, still without writing.
    again = _push(client, tenant, token, device, [stale]).json()["results"][0]
    assert again["status"] == "conflict" and again["replayed"] is True
    # Retrying with the current version succeeds.
    fresh = _op(
        "customer", "update", customer["id"], {"address": "Device address"}, expected_version=2
    )
    assert _push(client, tenant, token, device, [fresh]).json()["results"][0]["status"] == "applied"


def test_each_operation_is_its_own_transaction_and_failures_do_not_block_others(
    client, session_factory
):
    _, tenant, token, device = _device(client, session_factory, "push-atomic")
    category_id = str(uuid4())
    good = _op(
        "category",
        "create",
        category_id,
        {"name_en": "Snacks", "name_ar": "وجبات خفيفة", "slug": "snacks"},
    )
    bad = _op("customer", "create", str(uuid4()), {"name": "Nobody", "phone": "not-a-phone"})
    product_id = str(uuid4())
    product = _op(
        "tenant_product",
        "create",
        product_id,
        {
            "category_id": category_id,
            "name": "Chips",
            "barcode": "5280000000999",
            "unit_price": "1.5000",
            "currency": "USD",
            "price_basis": "PIECE",
        },
    )
    response = _push(client, tenant, token, device, [good, bad, product]).json()
    statuses = [row["status"] for row in response["results"]]
    assert statuses == ["applied", "rejected", "applied"], response
    assert response["results"][1]["error"]["code"] in {"INVALID_PHONE", "VALIDATION_ERROR"}
    assert response["results"][2]["entity_id"] == product_id
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SyncOperation)
                .where(SyncOperation.tenant_id == UUID(tenant))
            )
            == 3
        ), "applied and rejected results are both recorded for replay"
        assert (
            db.scalar(
                select(func.count()).select_from(Customer).where(Customer.tenant_id == UUID(tenant))
            )
            == 0
        )


def test_concurrent_identical_pushes_apply_one_effect(client, session_factory):
    _, tenant, token, device = _device(client, session_factory, "push-race")
    customer_id = str(uuid4())
    create = _op("customer", "create", customer_id, {"name": "Race", "phone": "+96170123488"})

    def send():
        return _push(client, tenant, token, device, [create]).json()["results"][0]["status"]

    with ThreadPoolExecutor(max_workers=3) as executor:
        statuses = list(executor.map(lambda _: send(), range(3)))
    assert statuses == ["applied", "applied", "applied"], statuses
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Customer).where(Customer.id == UUID(customer_id))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SyncChange)
                .where(
                    SyncChange.tenant_id == UUID(tenant), SyncChange.entity_id == UUID(customer_id)
                )
            )
            == 1
        )


def test_push_requires_registered_device_and_rejects_protocol_mismatch(client, session_factory):
    _, tenant, token = _owner_context(client, session_factory, "push-device")
    unknown = _push(
        client,
        tenant,
        token,
        str(uuid4()),
        [_op("customer", "create", str(uuid4()), {"name": "X", "phone": "+96170123477"})],
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "SYNC_DEVICE_NOT_REGISTERED"
    device = str(uuid4())
    assert _bootstrap(client, tenant, token, device).status_code == 200
    mismatch = client.post(
        f"/api/v1/sync/push?tenant_id={tenant}",
        headers=_auth(token),
        json={
            "device_installation_id": device,
            "protocol_version": 7,
            "operations": [
                _op("customer", "create", str(uuid4()), {"name": "X", "phone": "+96170123477"})
            ],
        },
    )
    assert mismatch.status_code == 409
