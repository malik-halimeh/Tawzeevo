"""FA-009 regression: one invoice header per tenant draft-create command (D-045)."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import _auth, _catalog, _draft_payload, _owner_context

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import Invoice
from tawzeevo_api.schemas.invoice_editor import InvoiceEditorDraftRequest
from tawzeevo_api.services.invoice_editor import create_editor_draft


def _count(session_factory, tenant: str) -> int:
    with session_factory() as db:
        return int(
            db.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.tenant_id == UUID(tenant))
            )
            or 0
        )


def test_same_create_command_returns_the_same_header_and_conflicts_on_a_different_request(
    client, session_factory
):
    _owner, tenant, token = _owner_context(client, session_factory, "fa009")
    _category, product, customer = _catalog(client, tenant, token)
    payload = _draft_payload(customer["id"], product["id"])

    first = client.post(f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=payload)
    assert first.status_code == 201, first.text
    replay = client.post(f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=payload)
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["current_revision_id"] == first.json()["current_revision_id"]
    assert _count(session_factory, tenant) == 1

    # Same command, different request (extra line) -> conflict, no new header.
    changed = dict(payload)
    changed["items"] = [payload["items"][0]]  # type: ignore[index]
    conflict = client.post(
        f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=changed
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert _count(session_factory, tenant) == 1

    # A new command creates a new header as before.
    fresh = client.post(
        f"/api/v1/invoices?tenant_id={tenant}",
        headers=_auth(token),
        json=_draft_payload(customer["id"], product["id"]),
    )
    assert fresh.status_code == 201 and fresh.json()["id"] != first.json()["id"]
    assert _count(session_factory, tenant) == 2


def test_concurrent_same_create_command_yields_one_header(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "fa009-race")
    _category, product, customer = _catalog(client, tenant, token)
    request = InvoiceEditorDraftRequest.model_validate(
        _draft_payload(customer["id"], product["id"])
    )

    def create() -> str:
        with session_factory() as db:
            try:
                response = create_editor_draft(
                    db, UUID(tenant), owner.id, request, fuzzy_threshold=Decimal("0.85")
                )
                return str(response.id)
            except AppError as error:  # pragma: no cover - the lock should prevent this
                db.rollback()
                return f"error:{error.code}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: create(), range(2)))
    assert ids[0] == ids[1] and not ids[0].startswith("error"), ids
    assert _count(session_factory, tenant) == 1


def test_create_commands_are_tenant_scoped(client, session_factory):
    _, tenant_a, token_a = _owner_context(client, session_factory, "fa009-a")
    _, tenant_b, token_b = _owner_context(client, session_factory, "fa009-b")
    _, product_a, customer_a = _catalog(client, tenant_a, token_a)
    _, product_b, customer_b = _catalog(client, tenant_b, token_b, barcode="5280000000029")
    command = str(uuid4())
    payload_b = _draft_payload(customer_b["id"], product_b["id"], command_id=command)
    payload_b["items"][0]["barcode"] = product_b["barcode"]  # type: ignore[index]
    a = client.post(
        f"/api/v1/invoices?tenant_id={tenant_a}",
        headers=_auth(token_a),
        json=_draft_payload(customer_a["id"], product_a["id"], command_id=command),
    )
    b = client.post(
        f"/api/v1/invoices?tenant_id={tenant_b}",
        headers=_auth(token_b),
        json=payload_b,
    )
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["id"] != b.json()["id"]
