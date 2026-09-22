"""Product facts for the Copilot tools (D-089): top products and catalog lookup.

Top products use the same semantics as the customer lifetime habits (D-069) but tenant-wide:
current revisions of CONFIRMED invoices confirmed in the period, per currency, value = line
totals (before invoice-level discounts/markups). `storefront_signals` is not reused because it
reads the first confirmed revision rather than the current one. There is no stock model, so no
availability is ever reported.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    Category,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    TenantProduct,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.analytics import resolve_period
from tawzeevo_api.services.invoice_editor import money


@dataclass(frozen=True)
class ProductTotal:
    currency: str
    product_name: str
    quantity: Decimal
    line_value: Decimal
    invoice_count: int


def top_products(
    db: Session,
    tenant_id: UUID,
    period_key: str,
    *,
    currency: str | None = None,
    limit: int = 5,
    as_of: datetime | None = None,
) -> list[ProductTotal]:
    set_tenant_scope(db, tenant_id)
    period = resolve_period(period_key, as_of)
    query = (
        select(
            InvoiceRevision.currency,
            InvoiceRevisionItem.tenant_product_id,
            InvoiceRevisionItem.product_name,
            InvoiceRevisionItem.quantity,
            InvoiceRevisionItem.line_total,
            Invoice.id,
        )
        .join(InvoiceRevision, InvoiceRevision.id == InvoiceRevisionItem.invoice_revision_id)
        .join(Invoice, Invoice.current_revision_id == InvoiceRevision.id)
        .where(
            Invoice.tenant_id == tenant_id,
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.confirmed_at < period.end,
        )
    )
    if period.start is not None:
        query = query.where(Invoice.confirmed_at >= period.start)
    if currency is not None:
        query = query.where(InvoiceRevision.currency == currency)
    quantity: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    value: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    invoices: dict[tuple[str, str], set[UUID]] = defaultdict(set)
    names: dict[tuple[str, str], str] = {}
    for code, product_id, name, qty, total, invoice_id in db.execute(query).all():
        key = (code, str(product_id) if product_id else f"manual:{name}")
        names.setdefault(key, name)
        quantity[key] += Decimal(qty)
        value[key] += Decimal(total)
        invoices[key].add(invoice_id)
    rows = sorted(
        (
            ProductTotal(
                currency=key[0],
                product_name=names[key],
                quantity=money(quantity[key]),
                line_value=money(value[key]),
                invoice_count=len(invoices[key]),
            )
            for key in quantity
        ),
        key=lambda r: (r.currency, -r.line_value, -r.quantity, r.product_name),
    )
    kept: list[ProductTotal] = []
    per_currency: dict[str, int] = defaultdict(int)
    for row in rows:
        if per_currency[row.currency] < limit:
            kept.append(row)
            per_currency[row.currency] += 1
    return kept


@dataclass(frozen=True)
class ProductMatch:
    name: str
    name_ar: str | None
    category: str | None
    unit_price: Decimal
    currency: str
    price_basis: str
    is_published: bool


def lookup_products(
    db: Session, tenant_id: UUID, text: str, *, currency: str | None = None, limit: int = 5
) -> list[ProductMatch]:
    set_tenant_scope(db, tenant_id)
    needle = f"%{text.strip()}%"
    query = (
        select(TenantProduct, Category.name_en)
        .outerjoin(Category, Category.id == TenantProduct.category_id)
        .where(
            TenantProduct.tenant_id == tenant_id,
            or_(TenantProduct.name.ilike(needle), TenantProduct.name_ar.ilike(needle)),
        )
        .order_by(func.lower(TenantProduct.name), TenantProduct.id)
        .limit(limit)
    )
    if currency is not None:
        query = query.where(TenantProduct.currency == currency)
    return [
        ProductMatch(
            name=product.name,
            name_ar=product.name_ar,
            category=category,
            unit_price=money(Decimal(product.unit_price)),
            currency=product.currency,
            price_basis=str(product.price_basis.value),
            is_published=bool(product.is_published),
        )
        for product, category in db.execute(query).all()
    ]
