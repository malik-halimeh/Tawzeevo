"""Read-only lists for the owner's customers page (D-101): every customer, and every invoice of one
customer. Revising, confirming and cancelling keep using the invoice endpoints and their rules."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import Customer, CustomerLedgerEntry, Invoice, InvoiceRevision
from tawzeevo_api.schemas.customer_ledger import CustomerBalanceResponse
from tawzeevo_api.schemas.customer_lists import (
    CustomerListResponse,
    CustomerListRow,
    CustomerListSort,
    InvoiceListResponse,
    InvoiceListRow,
)
from tawzeevo_api.services.cash_van import get_customer
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.text_search import normalize_search_text, normalized_search_expression


def _pages(total: int, limit: int) -> int:
    return (total + limit - 1) // limit if total else 0


def list_customers(
    db: Session,
    tenant_id: UUID,
    page: int,
    limit: int,
    *,
    q: str | None = None,
    sort: CustomerListSort = "name",
) -> CustomerListResponse:
    conditions = [Customer.tenant_id == tenant_id]
    if q is not None:
        query = normalize_search_text(q)
        matches = [normalized_search_expression(Customer.name).contains(query, autoescape=True)]
        digits = "".join(char for char in query if char in "0123456789")
        if len(digits) >= 3:
            matches.append(Customer.phone.contains(digits, autoescape=True))
            local_digits = digits.lstrip("0")
            if local_digits and local_digits != digits:
                matches.append(Customer.phone.contains(local_digits, autoescape=True))
        conditions.append(or_(*matches))
    total = int(db.scalar(select(func.count()).select_from(Customer).where(*conditions)) or 0)

    # Group signed entries before ranking: never add balances across currencies.
    positive_balances = (
        select(
            CustomerLedgerEntry.customer_id,
            CustomerLedgerEntry.currency,
            func.sum(CustomerLedgerEntry.signed_amount).label("balance"),
        )
        .where(CustomerLedgerEntry.tenant_id == tenant_id)
        .group_by(CustomerLedgerEntry.customer_id, CustomerLedgerEntry.currency)
        .having(func.sum(CustomerLedgerEntry.signed_amount) > 0)
    )
    statement = select(Customer).where(*conditions)
    if sort == "newest":
        statement = statement.order_by(Customer.created_at.desc(), Customer.id)
    elif sort == "owes_most":
        balances = positive_balances.subquery()
        largest = (
            select(balances.c.customer_id, func.max(balances.c.balance).label("balance"))
            .group_by(balances.c.customer_id)
            .subquery()
        )
        statement = statement.outerjoin(largest, largest.c.customer_id == Customer.id).order_by(
            largest.c.balance.desc().nulls_last(), func.lower(Customer.name), Customer.id
        )
    else:
        statement = statement.order_by(func.lower(Customer.name), Customer.id)
    customers = db.scalars(statement.offset((page - 1) * limit).limit(limit)).all()
    by_customer: dict[UUID, list[CustomerBalanceResponse]] = defaultdict(list)
    if customers:
        rows = db.execute(
            positive_balances.where(
                CustomerLedgerEntry.customer_id.in_([customer.id for customer in customers])
            ).order_by(CustomerLedgerEntry.currency)
        ).all()
        for customer_id, currency, balance in rows:
            by_customer[customer_id].append(
                CustomerBalanceResponse(currency=currency, balance=money(Decimal(balance)))
            )
    result = []
    for customer in customers:
        row = CustomerListRow.model_validate(customer)
        row.balances = by_customer[customer.id]
        result.append(row)
    return CustomerListResponse(
        page=page,
        limit=limit,
        total=total,
        total_pages=_pages(total, limit),
        customers=result,
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
