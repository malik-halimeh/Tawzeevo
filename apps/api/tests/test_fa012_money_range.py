"""FA-012 regression: oversized calculator results and monetary stages fail as validation errors,
never as server errors, and never persist partial rows (FI-01, 01_TECH_STACK.md Money)."""

from uuid import UUID

import pytest
from sqlalchemy import func, select
from test_invoice_editor import _auth, _catalog, _draft_payload, _owner_context

from tawzeevo_api.models import Invoice, InvoiceRevision


@pytest.mark.parametrize(
    "expression",
    [
        "123456789012345678901234567890",  # 30 digits, syntactically valid
        "9999999999 * 9999999999",  # product overflows the NUMERIC(20,4) integer part
        "10000000000000000",  # exactly the first unrepresentable magnitude
    ],
)
def test_calculator_rejects_unrepresentable_results_with_400(client, session_factory, expression):
    _owner, tenant, token = _owner_context(client, session_factory, "fa012-calc")
    response = client.post(
        f"/api/v1/invoices/calculator?tenant_id={tenant}",
        headers=_auth(token),
        json={"expression": expression},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "AMOUNT_OUT_OF_RANGE"


def test_calculator_accepts_largest_representable_value(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "fa012-max")
    response = client.post(
        f"/api/v1/invoices/calculator?tenant_id={tenant}",
        headers=_auth(token),
        json={"expression": "9999999999999999.9999"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["value"] == "9999999999999999.9999"


def test_oversized_line_and_invoice_totals_are_rejected_without_partial_rows(
    client, session_factory
):
    _owner, tenant, token = _owner_context(client, session_factory, "fa012-lines")
    _category, product, customer = _catalog(client, tenant, token)
    payload = _draft_payload(customer["id"], product["id"])
    payload["items"] = [payload["items"][0]]
    payload["items"][0]["quantity_expression"] = "9999999999999999"  # 12.5 x that overflows
    response = client.post(
        f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=payload
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "AMOUNT_OUT_OF_RANGE"

    payload["items"][0]["quantity_expression"] = "1"
    payload["invoice_markup_expression"] = "9999999999999999"
    response = client.post(
        f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=payload
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "AMOUNT_OUT_OF_RANGE"

    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(Invoice).where(Invoice.tenant_id == UUID(tenant))
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(InvoiceRevision)
                .where(InvoiceRevision.tenant_id == UUID(tenant))
            )
            == 0
        )
