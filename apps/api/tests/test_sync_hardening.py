"""P4-M6 property-style hardening (PHASE_04.md O): replay counts, crash between commits, device
identity alone is never authorization."""

from __future__ import annotations

from contextlib import suppress
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_sync_bootstrap import _bootstrap
from test_sync_push import _op, _push

from tawzeevo_api.models import (
    Customer,
    CustomerLedgerEntry,
    Invoice,
    Payment,
    SyncOperation,
)


def _device(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    device = str(uuid4())
    assert _bootstrap(client, tenant, token, device).status_code == 200
    return owner, tenant, token, device


def _count(session_factory, model, tenant):
    with session_factory() as db:
        return db.scalar(
            select(func.count()).select_from(model).where(model.tenant_id == UUID(tenant))
        )


def test_replaying_one_ten_and_a_hundred_times_applies_one_effect(client, session_factory):
    owner, tenant, token, device = _device(client, session_factory, "replay-100")
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    create_customer = _op(
        "customer", "create", str(uuid4()), {"name": "Replayed Maya", "phone": "+96170123400"}
    )
    receipt = _op(
        "payment",
        "receipt",
        str(uuid4()),
        {
            "customer_id": customer["id"],
            "amount": "3.0000",
            "currency": "USD",
            "paid_at": "2026-09-18T08:00:00+00:00",
        },
    )
    draft_payload = _confirmable_payload(customer["id"], product["id"])
    draft_payload.pop("client_command_id")
    draft_payload.pop("expected_predecessor_revision_id")
    create_invoice = _op("invoice", "create", str(uuid4()), draft_payload)

    for batch_size in (1, 10, 100):
        # The same three commands repeated inside one push and across pushes.
        batch = ([create_customer, receipt, create_invoice] * batch_size)[: max(3, batch_size)]
        response = _push(client, tenant, token, device, batch)
        assert response.status_code == 200, response.text
        statuses = {result["status"] for result in response.json()["results"]}
        assert statuses == {"applied"}
        assert _count(session_factory, Customer, tenant) == 2  # catalog customer + Maya
        assert _count(session_factory, Payment, tenant) == 1
        assert _count(session_factory, Invoice, tenant) == 1
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SyncOperation)
                .where(SyncOperation.tenant_id == UUID(tenant))
            )
            == 3
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(CustomerLedgerEntry)
                .where(
                    CustomerLedgerEntry.tenant_id == UUID(tenant),
                    CustomerLedgerEntry.entry_type != "INVOICE_CHARGE",
                )
            )
            == 1
        ), "one receipt ledger entry despite 111 deliveries"


def test_crash_between_the_financial_commit_and_the_result_commit_is_recovered(
    client, session_factory, monkeypatch
):
    """The financial service commits first; if the process dies before the push result is
    stored, the next replay completes the record and never charges twice."""
    from tawzeevo_api.services import sync_push

    owner, tenant, token, device = _device(client, session_factory, "crash-mid")
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    receipt = _op(
        "payment",
        "receipt",
        str(uuid4()),
        {
            "customer_id": customer["id"],
            "amount": "4.0000",
            "currency": "USD",
            "paid_at": "2026-09-18T08:00:00+00:00",
        },
    )
    real_apply = sync_push._apply_financial

    def crash_after_commit(db, tenant_id, actor, operation):
        real_apply(db, tenant_id, actor, operation)  # the service committed here
        raise RuntimeError("simulated process death before the result was stored")

    monkeypatch.setattr(sync_push, "_apply_financial", crash_after_commit)
    with suppress(RuntimeError):
        client.post(
            f"/api/v1/sync/push?tenant_id={tenant}",
            headers=_auth(token),
            json={"device_installation_id": device, "protocol_version": 1, "operations": [receipt]},
        )
    monkeypatch.setattr(sync_push, "_apply_financial", real_apply)
    with session_factory() as db:
        staged = db.scalar(select(SyncOperation).where(SyncOperation.tenant_id == UUID(tenant)))
        assert staged is not None and staged.result == {}, "staged record survived the crash"
    assert _count(session_factory, Payment, tenant) == 1

    recovered = _push(client, tenant, token, device, [receipt]).json()["results"][0]
    assert recovered["status"] == "applied", recovered
    assert recovered["projection"]["amount"] == "4.0000"
    assert _count(session_factory, Payment, tenant) == 1
    again = _push(client, tenant, token, device, [receipt]).json()["results"][0]
    assert again["replayed"] is True and again["projection"]["id"] == recovered["projection"]["id"]
    with session_factory() as db:
        record = db.scalar(select(SyncOperation).where(SyncOperation.tenant_id == UUID(tenant)))
        assert record is not None and record.result["status"] == "applied"


def test_a_device_id_alone_is_never_authorization(client, session_factory):
    _owner, tenant, token, device = _device(client, session_factory, "device-alone")
    _other_owner, other_tenant, other_token = _owner_context(client, session_factory, "other-dev")
    operation = _op(
        "customer", "create", str(uuid4()), {"name": "Intruder", "phone": "+96170123401"}
    )
    # No token, a registered device id: denied.
    anonymous = client.post(
        f"/api/v1/sync/push?tenant_id={tenant}",
        json={"device_installation_id": device, "protocol_version": 1, "operations": [operation]},
    )
    assert anonymous.status_code == 401
    # A valid session of another business with this device id: denied for this tenant.
    crossed = _push(client, tenant, other_token, device, [operation])
    assert crossed.status_code == 403
    # The same device id used against the other business without bootstrapping there: denied.
    unregistered = _push(client, other_tenant, other_token, device, [operation])
    assert unregistered.status_code == 404, unregistered.text
    assert unregistered.json()["detail"]["code"] == "SYNC_DEVICE_NOT_REGISTERED"
    assert _count(session_factory, Customer, tenant) == 0
    assert _count(session_factory, Customer, other_tenant) == 0
    pull = client.get(
        f"/api/v1/sync/pull?tenant_id={tenant}&device_installation_id={device}&cursor=0"
    )
    assert pull.status_code == 401
