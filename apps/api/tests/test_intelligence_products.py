"""D-089 product facts: top products report line sales before invoice-level adjustments (the sum
of stored line totals of current confirmed revisions) and are never presented as net sales."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from test_invoice_editor import _attach_latest_cost, _catalog, _owner_context
from test_procurement import _confirm_invoice

from tawzeevo_api.models import Invoice, InvoiceRevisionItem
from tawzeevo_api.services.intelligence.copilot.tools import TOOLS
from tawzeevo_api.services.intelligence.products import lookup_products, top_products


def test_top_products_are_line_sales_before_invoice_adjustments(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "intprod")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    # The helper payload carries an invoice-level discount (1) and markup (0.5).
    invoice = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "3")
    with session_factory() as db:
        row = db.get(Invoice, UUID(invoice["id"]))
        assert row is not None
        line_total = sum(
            Decimal(item.line_total)
            for item in db.query(InvoiceRevisionItem).filter_by(
                invoice_revision_id=row.current_revision_id
            )
        )
        (top,) = top_products(db, UUID(tenant), "30d")
        matches = lookup_products(db, UUID(tenant), "cedar")
    assert top.line_sales_before_invoice_adjustments == line_total
    assert top.line_sales_before_invoice_adjustments != Decimal(invoice["net_sales"])
    assert Decimal(invoice["net_sales"]) == line_total - Decimal("1") + Decimal("0.5")
    assert top.is_catalog_product and top.quantity == Decimal("3.0000")
    assert [m.name for m in matches] == ["Cedar Water"]
    assert not {"stock", "available", "availability"} & set(vars(matches[0]))
    description = TOOLS["get_top_products"].description
    assert "before invoice-level" in description and "not net sales" in description
