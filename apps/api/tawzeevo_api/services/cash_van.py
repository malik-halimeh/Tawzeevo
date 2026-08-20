from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    Category,
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    ProductPriceBasis,
    TenantProduct,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.schemas.cash_van import (
    CategoryCreateRequest,
    CustomerCreateRequest,
    CustomerResponse,
    DraftInvoiceCreateRequest,
    DraftInvoiceResponse,
    InvoiceItemResponse,
    TenantProductCreateRequest,
    TenantProductResponse,
)

MONEY_QUANTUM = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _set_tenant_scope(db: Session, tenant_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def _commit_and_restore_scope(db: Session, tenant_id: UUID) -> None:
    db.commit()
    _set_tenant_scope(db, tenant_id)


def create_customer(db: Session, tenant_id: UUID, request: CustomerCreateRequest) -> Customer:
    customer = Customer(
        tenant_id=tenant_id,
        name=request.name,
        phone=normalize_phone(request.phone),
        phone_raw=request.phone,
        address=request.address,
    )
    db.add(customer)
    _commit_and_restore_scope(db, tenant_id)
    db.refresh(customer)
    return customer


def get_customer(db: Session, tenant_id: UUID, customer_id: UUID) -> Customer:
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    )
    if customer is None:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
    return customer


def search_customers_by_phone(db: Session, tenant_id: UUID, phone: str) -> list[Customer]:
    try:
        normalized_phone = normalize_phone(phone)
    except InvalidPhoneNumberError as exc:
        raise AppError(400, "INVALID_PHONE", "Phone number is invalid") from exc
    return list(
        db.scalars(
            select(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.phone == normalized_phone)
            .order_by(Customer.created_at.asc(), Customer.id.asc())
        )
    )


def create_category(db: Session, tenant_id: UUID, request: CategoryCreateRequest) -> Category:
    category = Category(tenant_id=tenant_id, name=request.name)
    db.add(category)
    _commit_and_restore_scope(db, tenant_id)
    db.refresh(category)
    return category


def get_category(db: Session, tenant_id: UUID, category_id: UUID) -> Category:
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id)
    )
    if category is None:
        raise AppError(404, "CATEGORY_NOT_FOUND", "Category was not found")
    return category


def list_categories(db: Session, tenant_id: UUID) -> list[Category]:
    return list(
        db.scalars(
            select(Category)
            .where(Category.tenant_id == tenant_id)
            .order_by(Category.created_at.asc(), Category.id.asc())
        )
    )


def product_response(product: TenantProduct) -> TenantProductResponse:
    if product.price_basis is ProductPriceBasis.PIECE:
        piece_price = _money(product.unit_price)
        box_price = (
            _money(product.unit_price * product.pieces_per_box)
            if product.pieces_per_box is not None
            else None
        )
    else:
        if product.pieces_per_box is None:
            raise RuntimeError("BOX product is missing pieces_per_box")
        piece_price = _money(product.unit_price / product.pieces_per_box)
        box_price = _money(product.unit_price)
    return TenantProductResponse(
        id=product.id,
        tenant_id=product.tenant_id,
        category_id=product.category_id,
        name=product.name,
        barcode=product.barcode,
        unit_price=_money(product.unit_price),
        currency=product.currency,
        price_basis=product.price_basis,
        pieces_per_box=product.pieces_per_box,
        piece_price=piece_price,
        box_price=box_price,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def create_product(
    db: Session, tenant_id: UUID, request: TenantProductCreateRequest
) -> TenantProduct:
    get_category(db, tenant_id, request.category_id)
    existing = db.scalar(
        select(TenantProduct.id).where(
            TenantProduct.tenant_id == tenant_id,
            TenantProduct.barcode == request.barcode,
        )
    )
    if existing is not None:
        raise AppError(409, "BARCODE_ALREADY_EXISTS", "Barcode already exists in this tenant")
    product = TenantProduct(
        tenant_id=tenant_id,
        category_id=request.category_id,
        name=request.name,
        barcode=request.barcode,
        unit_price=_money(request.unit_price),
        currency=request.currency,
        price_basis=request.price_basis,
        pieces_per_box=request.pieces_per_box,
    )
    db.add(product)
    try:
        _commit_and_restore_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409, "BARCODE_ALREADY_EXISTS", "Barcode already exists in this tenant"
        ) from exc
    db.refresh(product)
    return product


def get_product(db: Session, tenant_id: UUID, product_id: UUID) -> TenantProduct:
    product = db.scalar(
        select(TenantProduct).where(
            TenantProduct.id == product_id, TenantProduct.tenant_id == tenant_id
        )
    )
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product was not found")
    return product


def get_product_by_barcode(db: Session, tenant_id: UUID, barcode: str) -> TenantProduct:
    product = db.scalar(
        select(TenantProduct).where(
            TenantProduct.tenant_id == tenant_id,
            TenantProduct.barcode == barcode.strip(),
        )
    )
    if product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product was not found")
    return product


def _invoice_response(db: Session, tenant_id: UUID, invoice: Invoice) -> DraftInvoiceResponse:
    customer = get_customer(db, tenant_id, invoice.customer_id)
    items = list(
        db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == invoice.id, InvoiceItem.tenant_id == tenant_id)
            .order_by(InvoiceItem.created_at.asc(), InvoiceItem.id.asc())
        )
    )
    return DraftInvoiceResponse(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        customer=CustomerResponse.model_validate(customer),
        status=invoice.status,
        currency=invoice.currency,
        subtotal=invoice.subtotal,
        items=[InvoiceItemResponse.model_validate(item) for item in items],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def create_draft_invoice(
    db: Session, tenant_id: UUID, request: DraftInvoiceCreateRequest
) -> DraftInvoiceResponse:
    get_customer(db, tenant_id, request.customer_id)
    product_ids = {item.product_id for item in request.items}
    products = list(
        db.scalars(
            select(TenantProduct).where(
                TenantProduct.tenant_id == tenant_id,
                TenantProduct.id.in_(product_ids),
            )
        )
    )
    products_by_id = {product.id: product for product in products}
    missing_product = next(
        (item.product_id for item in request.items if item.product_id not in products_by_id), None
    )
    if missing_product is not None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Product was not found")

    currencies = {product.currency for product in products}
    if len(currencies) != 1:
        raise AppError(
            400,
            "CURRENCY_MISMATCH",
            "A draft invoice cannot combine products with different currencies",
        )
    currency = currencies.pop()
    invoice = Invoice(
        tenant_id=tenant_id,
        customer_id=request.customer_id,
        status=InvoiceStatus.DRAFT,
        currency=currency,
        subtotal=Decimal("0.0000"),
    )
    db.add(invoice)
    db.flush()

    subtotal = Decimal("0.0000")
    for requested_item in request.items:
        product = products_by_id[requested_item.product_id]
        line_total = _money(product.unit_price * requested_item.quantity)
        subtotal += line_total
        db.add(
            InvoiceItem(
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                product_id=product.id,
                product_name=product.name,
                barcode=product.barcode,
                quantity=requested_item.quantity,
                price_basis=product.price_basis,
                unit_price=product.unit_price,
                line_total=line_total,
            )
        )
    invoice.subtotal = _money(subtotal)
    _commit_and_restore_scope(db, tenant_id)
    db.refresh(invoice)
    return _invoice_response(db, tenant_id, invoice)


def get_draft_invoice(db: Session, tenant_id: UUID, invoice_id: UUID) -> DraftInvoiceResponse:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    return _invoice_response(db, tenant_id, invoice)
