"""FA-005 regression: one active confirmed-only public link; cancellation revokes (D-042, FI-27)."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _owner_context,
)
from test_public_invoices import _resolve

from tawzeevo_api.models import PublicInvoiceCapability
from tawzeevo_api.services.public_invoices import issue_capability


def _active_count(session_factory, invoice_id: str) -> int:
    with session_factory() as db:
        return int(
            db.scalar(
                select(func.count())
                .select_from(PublicInvoiceCapability)
                .where(
                    PublicInvoiceCapability.invoice_id == UUID(invoice_id),
                    PublicInvoiceCapability.revoked_at.is_(None),
                )
            )
            or 0
        )


def test_links_require_confirmation_are_single_active_and_die_with_cancellation(
    client, session_factory
):
    (
        owner,
        tenant,
        token,
    ) = _owner_context(client, session_factory, "fa005")
    _, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    headers = _auth(token)
    draft = client.post(
        f"/api/v1/invoices?tenant_id={tenant}",
        headers=headers,
        json=_confirmable_payload(customer["id"], product["id"]),
    ).json()
    path = f"/api/v1/invoices/{draft['id']}/capabilities"

    denied = client.post(f"{path}?tenant_id={tenant}", headers=headers)
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"]["code"] == "INVOICE_NOT_CONFIRMED"
    assert _active_count(session_factory, draft["id"]) == 0

    confirmed = client.post(
        f"/api/v1/invoices/{draft['id']}/confirm?tenant_id={tenant}",
        headers=headers,
        json={"expected_revision_id": draft["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text

    first = client.post(f"{path}?tenant_id={tenant}", headers=headers).json()
    assert _resolve(client, first).status_code == 200
    second = client.post(f"{path}?tenant_id={tenant}", headers=headers).json()
    assert _resolve(client, first).status_code == 404, "issuing again replaces the old link"
    assert _resolve(client, second).status_code == 200
    assert _active_count(session_factory, draft["id"]) == 1
    listed = client.get(f"{path}?tenant_id={tenant}", headers=headers).json()
    assert {row["id"]: row["revoked_at"] is None for row in listed} == {
        first["id"]: False,
        second["id"]: True,
    }

    rotated = client.post(f"{path}/{second['id']}/rotate?tenant_id={tenant}", headers=headers)
    assert rotated.status_code == 201, rotated.text
    assert _resolve(client, second).status_code == 404
    assert _resolve(client, rotated.json()).status_code == 200
    assert _active_count(session_factory, draft["id"]) == 1

    cancelled = client.post(
        f"/api/v1/invoices/{draft['id']}/cancel?tenant_id={tenant}",
        headers=headers,
        json={"idempotency_key": str(uuid4()), "reason": "Customer withdrew"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert _resolve(client, rotated.json()).status_code == 404, "cancellation revokes access"
    assert _active_count(session_factory, draft["id"]) == 0
    after_cancel = client.post(f"{path}?tenant_id={tenant}", headers=headers)
    assert after_cancel.status_code == 409, after_cancel.text


def test_concurrent_issue_leaves_exactly_one_active_link(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "fa005-race")
    _, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    headers = _auth(token)
    draft = client.post(
        f"/api/v1/invoices?tenant_id={tenant}",
        headers=headers,
        json=_confirmable_payload(customer["id"], product["id"]),
    ).json()
    assert (
        client.post(
            f"/api/v1/invoices/{draft['id']}/confirm?tenant_id={tenant}",
            headers=headers,
            json={"expected_revision_id": draft["current_revision_id"]},
        ).status_code
        == 200
    )

    def issue() -> int:
        with session_factory() as db:
            issue_capability(db, UUID(tenant), owner.id, UUID(draft["id"]))
            return 1

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sum(executor.map(lambda _: issue(), range(2))) == 2
    assert _active_count(session_factory, draft["id"]) == 1
