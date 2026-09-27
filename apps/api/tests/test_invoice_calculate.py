"""D-107: calculating an invoice returns the saved-draft totals and writes nothing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from test_invoice_editor import _auth, _catalog, _draft_payload, _owner_context

from tawzeevo_api.models import AuditEvent, Invoice, InvoiceRevision


def _counts(session_factory, tenant):
    with session_factory() as db:
        return tuple(
            db.scalar(
                select(func.count()).select_from(model).where(model.tenant_id == UUID(tenant))
            )
            for model in (Invoice, InvoiceRevision, AuditEvent)
        )


def test_calculate_matches_the_saved_draft_and_writes_nothing(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "calc")
    _category, product, customer = _catalog(client, tenant, token)
    payload = _draft_payload(customer["id"], product["id"])
    body = {
        key: value
        for key, value in payload.items()
        if key not in {"client_command_id", "expected_predecessor_revision_id"}
    }
    before = _counts(session_factory, tenant)
    calculated = client.post(
        "/api/v1/invoices/calculate", params={"tenant_id": tenant}, headers=_auth(token), json=body
    )
    assert calculated.status_code == 200, calculated.text
    assert _counts(session_factory, tenant) == before  # nothing written
    saved = client.post(
        "/api/v1/invoices", params={"tenant_id": tenant}, headers=_auth(token), json=payload
    ).json()
    result = calculated.json()
    for key in ("subtotal", "discount_total", "markup_total", "net_sales", "total_due", "currency"):
        assert result[key] == saved[key], key
    assert result["prior_balance"] == saved["prior_balance"]
    assert [line["line_total"] for line in result["lines"]] == [
        item["line_total"] for item in saved["items"]
    ]

    # Same validation as saving; command ids are not accepted here.
    bad = client.post(
        "/api/v1/invoices/calculate",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={**body, "invoice_discount_expression": "1000000"},
    )
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "NEGATIVE_INVOICE_TOTAL"
    assert (
        client.post(
            "/api/v1/invoices/calculate",
            params={"tenant_id": tenant},
            headers=_auth(token),
            json=payload,
        ).status_code
        == 422
    )
