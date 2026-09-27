"""Read-only lists for the owner's customers page (D-101): every customer, and every invoice of one
customer. Revising, confirming and cancelling keep using the invoice endpoints and their rules."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import Customer, Invoice, InvoiceRevision
from tawzeevo_api.schemas.cash_van import CustomerResponse
from tawzeevo_api.schemas.customer_lists import (
    CustomerListResponse,
    InvoiceListResponse,
    InvoiceListRow,
)
from tawzeevo_api.services.cash_van import get_customer
from tawzeevo_api.services.invoice_editor import money


def _pages(total: int, limit: int) -> int:
    return (total + limit - 1) // limit if total else 0


def list_customers(db: Session, tenant_id: UUID, page: int, limit: int) -> CustomerListResponse:
    total = int(
        db.scalar(select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id))
        or 0
    )
    customers = db.scalars(
        select(Customer)
        .where(Customer.tenant_id == tenant_id)
        .order_by(func.lower(Customer.name), Customer.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return CustomerListResponse(
        page=page,
        limit=limit,
        total=total,
        total_pages=_pages(total, limit),
        customers=[CustomerResponse.model_validate(customer) for customer in customers],
    )


def list_customer_invoices(
    db: Session, tenant_id: UUID, customer_id: UUID, page: int, limit: int
) -> InvoiceListResponse:
    """Invoices of one customer (drafts, confirmed and cancelled), newest first by the date that
    matters: confirmation for confirmed invoices, creation otherwise."""
    get_customer(db, tenant_id, customer_id)
    conditions = (Invoice.tenant_id == tenant_id, Invoice.customer_id == customer_id)
    total = int(db.scalar(select(func.count()).select_from(Invoice).where(*conditions)) or 0)
    rows = db.execute(
        select(Invoice, InvoiceRevision)
        .join(
            InvoiceRevision,
            (InvoiceRevision.id == Invoice.current_revision_id)
            & (InvoiceRevision.tenant_id == Invoice.tenant_id),
        )
        .where(*conditions)
        .order_by(func.coalesce(Invoice.confirmed_at, Invoice.created_at).desc(), Invoice.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return InvoiceListResponse(
        page=page,
        limit=limit,
        total=total,
        total_pages=_pages(total, limit),
        invoices=[
            InvoiceListRow(
                id=invoice.id,
                status=invoice.status,
                official_invoice_number=invoice.official_invoice_number,
                confirmed_at=invoice.confirmed_at,
                created_at=invoice.created_at,
                currency=revision.currency,
                net_sales=money(revision.net_sales),
                total_due=money(revision.amount_due_display),
                server_revision_number=revision.server_revision_number,
            )
            for invoice, revision in rows
        ],
    )
