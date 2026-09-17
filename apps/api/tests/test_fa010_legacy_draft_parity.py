"""FA-010 regression: the legacy tenant-nested draft route stores the same prior-balance and due
snapshot as the production editor (D-037, FI-26)."""

from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from test_fa008_obligations import _opening
from test_invoice_editor import _auth, _catalog, _draft_payload, _owner_context

from tawzeevo_api.models import InvoiceRevision


@pytest.mark.parametrize(
    ("label", "opening"), [("debt", "10.0000"), ("credit", "-4.2500"), ("none", None)]
)
def test_legacy_and_editor_drafts_share_prior_balance_snapshot(
    client, session_factory, label: str, opening: str | None
) -> None:
    _owner, tenant, token = _owner_context(client, session_factory, f"fa010-{label}")
    _category, product, customer = _catalog(client, tenant, token)
    if opening is not None:
        _opening(client, tenant, token, customer["id"], opening)
        # A different currency must never leak into the USD snapshot.
        _opening(client, tenant, token, customer["id"], "900000.0000", currency="LBP")
    expected_prior = Decimal(opening or "0")

    legacy = client.post(
        f"/api/v1/tenants/{tenant}/invoices",
        headers=_auth(token),
        json={
            "customer_id": customer["id"],
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert legacy.status_code == 201, legacy.text
    editor_payload = _draft_payload(customer["id"], product["id"])
    editor_payload["items"] = [editor_payload["items"][0]]
    editor_payload["items"][0]["quantity_expression"] = "1"
    editor_payload["items"][0]["line_discount_expression"] = "0"
    editor_payload["items"][0]["line_markup_expression"] = "0"
    editor_payload["invoice_discount_expression"] = "0"
    editor_payload["invoice_markup_expression"] = "0"
    editor = client.post(
        f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=editor_payload
    )
    assert editor.status_code == 201, editor.text

    with session_factory() as db:
        legacy_revision = db.scalar(
            select(InvoiceRevision).where(InvoiceRevision.invoice_id == UUID(legacy.json()["id"]))
        )
        editor_revision = db.scalar(
            select(InvoiceRevision).where(InvoiceRevision.invoice_id == UUID(editor.json()["id"]))
        )
        assert legacy_revision is not None and editor_revision is not None
        assert legacy_revision.prior_balance_snapshot == expected_prior
        assert legacy_revision.prior_balance_snapshot == editor_revision.prior_balance_snapshot
        assert legacy_revision.net_sales == editor_revision.net_sales
        assert legacy_revision.amount_due_display == expected_prior + legacy_revision.net_sales
        assert legacy_revision.amount_due_display == editor_revision.amount_due_display
