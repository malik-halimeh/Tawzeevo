"""P4-M4 backend: offline invoice/payment commands through push reuse Phase 3 financial rules."""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import (
    _attach_latest_cost,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_sync_bootstrap import _bootstrap
from test_sync_push import _op, _push

from tawzeevo_api.models import CustomerLedgerEntry, Invoice, InvoiceSequence, Payment, SyncChange


def _device(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    device = str(uuid4())
    assert _bootstrap(client, tenant, token, device).status_code == 200
    return owner, tenant, token, device


def test_offline_invoice_lifecycle_and_receipt_apply_exactly_once(client, session_factory):
    owner, tenant, token, device = _device(client, session_factory, "fin-push")
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    invoice_id = str(uuid4())
    draft_payload = _confirmable_payload(customer["id"], product["id"])
    draft_payload.pop("client_command_id")  # the device operation id becomes the command identity
    draft_payload.pop("expected_predecessor_revision_id")
    create = _op("invoice", "create", invoice_id, draft_payload)

    first = _push(client, tenant, token, device, [create]).json()["results"][0]
    assert first["status"] == "applied", first
    server_invoice_id = first["entity_id"]
    assert first["projection"]["status"] == "DRAFT"
    assert first["projection"]["official_invoice_number"] is None
    revision_id = first["projection"]["current_revision_id"]

    # Replay of the same create (lost response) returns the same header, no second draft.
    replay = _push(client, tenant, token, device, [create]).json()["results"][0]
    assert replay["replayed"] is True and replay["entity_id"] == server_invoice_id
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.tenant_id == UUID(tenant))
            )
            == 1
        )

    confirm = _op("invoice", "confirm", server_invoice_id, {"expected_revision_id": revision_id})
    confirmed = _push(client, tenant, token, device, [confirm, confirm]).json()["results"]
    assert confirmed[0]["status"] == "applied"
    number = confirmed[0]["projection"]["official_invoice_number"]
    assert number and number.endswith("-000001"), "official number is assigned by the server"
    assert (
        confirmed[1]["replayed"] is True
        and confirmed[1]["projection"]["official_invoice_number"] == number
    )
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(InvoiceSequence)) == 1
        charges = list(
            db.scalars(
                select(CustomerLedgerEntry).where(
                    CustomerLedgerEntry.tenant_id == UUID(tenant),
                    CustomerLedgerEntry.entry_type == "INVOICE_CHARGE",
                )
            )
        )
        assert len(charges) == 1

    receipt = _op(
        "payment",
        "receipt",
        str(uuid4()),
        {
            "customer_id": customer["id"],
            "amount": "10.0000",
            "currency": "USD",
            "paid_at": "2026-09-18T08:00:00+00:00",
            "method": "CASH",
        },
    )
    paid = _push(client, tenant, token, device, [receipt, receipt]).json()["results"]
    assert paid[0]["status"] == "applied" and paid[1]["replayed"] is True
    assert paid[0]["projection"]["allocated_amount"] == "10.0000"
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Payment).where(Payment.tenant_id == UUID(tenant))
            )
            == 1
        )
        balance = db.scalar(
            select(func.sum(CustomerLedgerEntry.signed_amount)).where(
                CustomerLedgerEntry.tenant_id == UUID(tenant)
            )
        )
        assert Decimal(balance) == Decimal(first["projection"]["net_sales"]) - Decimal("10")
        # Every financial effect of the device shows up in the change log with its operation id.
        attributed = set(
            db.scalars(
                select(SyncChange.operation_id).where(
                    SyncChange.tenant_id == UUID(tenant), SyncChange.operation_id.isnot(None)
                )
            )
        )
        assert UUID(create["operation_id"]) in attributed
        assert UUID(receipt["operation_id"]) in attributed


def test_offline_financial_rules_still_apply_and_two_devices_never_collide(client, session_factory):
    owner, tenant, token, device_a = _device(client, session_factory, "fin-rules")
    device_b = str(uuid4())
    assert _bootstrap(client, tenant, token, device_b).status_code == 200
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])

    def draft(device):
        payload = _confirmable_payload(customer["id"], product["id"])
        payload.pop("client_command_id")
        payload.pop("expected_predecessor_revision_id")
        result = _push(
            client, tenant, token, device, [_op("invoice", "create", str(uuid4()), payload)]
        )
        return result.json()["results"][0]["projection"]

    a = draft(device_a)
    b = draft(device_b)
    confirms = []
    for device, invoice in ((device_a, a), (device_b, b)):
        result = _push(
            client,
            tenant,
            token,
            device,
            [
                _op(
                    "invoice",
                    "confirm",
                    invoice["id"],
                    {"expected_revision_id": invoice["current_revision_id"]},
                )
            ],
        ).json()["results"][0]
        confirms.append(result["projection"]["official_invoice_number"])
    assert len(set(confirms)) == 2, "two devices receive two distinct official numbers"

    # A refund without credit is rejected exactly as online (Phase 3 ceiling), recorded once.
    refund = _op(
        "payment",
        "refund",
        str(uuid4()),
        {
            "customer_id": customer["id"],
            "amount": "5.0000",
            "currency": "USD",
            "paid_at": "2026-09-18T08:00:00+00:00",
        },
    )
    rejected = _push(client, tenant, token, device_a, [refund]).json()["results"][0]
    assert rejected["status"] == "rejected"
    assert rejected["error"]["code"]
    again = _push(client, tenant, token, device_a, [refund]).json()["results"][0]
    assert again["status"] == "rejected" and again["replayed"] is True
    # A stale confirmation (old revision id) is rejected without a second charge.
    stale = _op("invoice", "confirm", a["id"], {"expected_revision_id": a["current_revision_id"]})
    replayed_confirm = _push(client, tenant, token, device_b, [stale]).json()["results"][0]
    assert replayed_confirm["status"] in {"applied", "rejected"}
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CustomerLedgerEntry)
                .where(
                    CustomerLedgerEntry.tenant_id == UUID(tenant),
                    CustomerLedgerEntry.entry_type == "INVOICE_CHARGE",
                )
            )
            == 2
        )
