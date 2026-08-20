from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.database import SessionLocal
from tawzeevo_api.dependencies import resolve_tenant_context
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    Category,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    ProductPriceBasis,
    TenantProduct,
    TenantRole,
    User,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone

DEMO_BARCODE = "TZW-P1-DEMO-001"


@dataclass(frozen=True)
class DemoSeedResult:
    tenant_id: UUID
    customer_id: UUID
    category_id: UUID
    product_id: UUID
    invoice_id: UUID


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description=(
            "Add synthetic Phase 1 Cash Van demo rows to an existing approved owner tenant."
        )
    )
    command.add_argument("--owner-email", required=True)
    command.add_argument("--tenant-id", required=True, type=UUID)
    command.add_argument("--customer-phone", required=True)
    command.add_argument("--currency", required=True)
    return command


def seed_demo_data(
    db: Session,
    *,
    owner_email: str,
    tenant_id: UUID,
    customer_phone: str,
    currency: str,
) -> DemoSeedResult:
    normalized_email = owner_email.strip().lower()
    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise AppError(400, "INVALID_CURRENCY", "Currency must be a three-letter ISO code")
    try:
        normalized_phone = normalize_phone(customer_phone.strip())
    except InvalidPhoneNumberError as exc:
        raise AppError(400, "INVALID_PHONE", "Customer phone is invalid") from exc

    owner = db.scalar(
        select(User).where(
            User.email == normalized_email,
            User.is_deleted.is_(False),
        )
    )
    if owner is None:
        raise AppError(404, "OWNER_NOT_FOUND", "An active owner account was not found")
    context = resolve_tenant_context(db, owner, tenant_id)
    if context.membership.role is not TenantRole.OWNER:
        raise AppError(403, "TENANT_OWNER_REQUIRED", "Tenant owner access is required")
    existing = db.scalar(
        select(TenantProduct.id).where(
            TenantProduct.tenant_id == tenant_id,
            TenantProduct.barcode == DEMO_BARCODE,
        )
    )
    if existing is not None:
        raise AppError(409, "DEMO_DATA_ALREADY_EXISTS", "Demo data already exists for this tenant")

    category = Category(tenant_id=tenant_id, name="Demo beverages")
    customer = Customer(
        tenant_id=tenant_id,
        name="Demo Customer",
        phone=normalized_phone,
        phone_raw=customer_phone.strip(),
        address="Synthetic demo address",
    )
    db.add_all([category, customer])
    db.flush()

    unit_price = Decimal("2.5000")
    quantity = Decimal("4.0000")
    subtotal = Decimal("10.0000")
    product = TenantProduct(
        tenant_id=tenant_id,
        category_id=category.id,
        name="Demo bottled water",
        barcode=DEMO_BARCODE,
        unit_price=unit_price,
        currency=normalized_currency,
        price_basis=ProductPriceBasis.PIECE,
        pieces_per_box=12,
    )
    db.add(product)
    db.flush()
    invoice = Invoice(
        tenant_id=tenant_id,
        customer_id=customer.id,
        status=InvoiceStatus.DRAFT,
        currency=normalized_currency,
        subtotal=subtotal,
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceItem(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            product_id=product.id,
            product_name=product.name,
            barcode=product.barcode,
            quantity=quantity,
            price_basis=product.price_basis,
            unit_price=unit_price,
            line_total=subtotal,
        )
    )
    db.commit()
    return DemoSeedResult(
        tenant_id=tenant_id,
        customer_id=customer.id,
        category_id=category.id,
        product_id=product.id,
        invoice_id=invoice.id,
    )


def main(db_factory: sessionmaker[Session] | None = None) -> int:
    arguments = parser().parse_args()
    factory = db_factory or SessionLocal
    try:
        with factory() as db:
            result = seed_demo_data(
                db,
                owner_email=arguments.owner_email,
                tenant_id=arguments.tenant_id,
                customer_phone=arguments.customer_phone,
                currency=arguments.currency,
            )
    except AppError as exc:
        print(f"Demo data was not created: {exc.code} — {exc.message}")
        return 1
    print(
        "Created synthetic demo data for tenant "
        f"{result.tenant_id}; draft invoice {result.invoice_id}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
