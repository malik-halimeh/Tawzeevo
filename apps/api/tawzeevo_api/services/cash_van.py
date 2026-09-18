from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    BarcodeOwnership,
    BarcodePackageLevel,
    Category,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    MasterBarcode,
    MasterCategory,
    MasterProduct,
    MasterProductImage,
    MediaOwnership,
    ProductPriceBasis,
    TenantBarcode,
    TenantProduct,
    TenantProductImage,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.cash_van import (
    BarcodeCreateRequest,
    BarcodeLookupResponse,
    BarcodeResponse,
    CategoryCreateRequest,
    CategoryUpdateRequest,
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
    DraftInvoiceCreateRequest,
    DraftInvoiceItemCreateRequest,
    DraftInvoiceResponse,
    InvoiceItemResponse,
    MasterProductResponse,
    ProductGradePriceResponse,
    ProductImageResponse,
    TenantProductCreateRequest,
    TenantProductResponse,
    TenantProductUpdateRequest,
)
from tawzeevo_api.services.media import list_master_product_images, list_tenant_product_images
from tawzeevo_api.services.pricing import (
    derive_counterpart_prices,
    list_product_grade_prices,
    quantize_money,
    resolve_product_pricing,
)

_money = quantize_money


def create_customer(db: Session, tenant_id: UUID, request: CustomerCreateRequest) -> Customer:
    customer = Customer(
        tenant_id=tenant_id,
        name=request.name,
        phone=normalize_phone(request.phone),
        phone_raw=request.phone,
        address=request.address,
        latitude=request.latitude,
        longitude=request.longitude,
        grade=request.grade,
    )
    db.add(customer)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(customer)
    return customer


def update_customer(
    db: Session,
    tenant_id: UUID,
    customer_id: UUID,
    request: CustomerUpdateRequest,
) -> Customer:
    customer = get_customer(db, tenant_id, customer_id)
    values = request.model_dump(exclude_unset=True)
    if "phone" in values:
        raw_phone = values["phone"]
        customer.phone = normalize_phone(raw_phone)
        customer.phone_raw = raw_phone
        values.pop("phone")
    for field_name, value in values.items():
        setattr(customer, field_name, value)
    commit_and_restore_tenant_scope(db, tenant_id)
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
    if request.master_category_id is not None:
        master_category = db.scalar(
            select(MasterCategory).where(
                MasterCategory.id == request.master_category_id,
                MasterCategory.is_active.is_(True),
            )
        )
        if master_category is None:
            raise AppError(404, "MASTER_CATEGORY_NOT_FOUND", "Master category was not found")
    category = Category(
        tenant_id=tenant_id,
        master_category_id=request.master_category_id,
        name_en=request.name_en,
        name_ar=request.name_ar,
        slug=request.slug,
        display_order=request.display_order,
        is_active=True,
    )
    db.add(category)
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "CATEGORY_SLUG_ALREADY_EXISTS",
            "Category slug already exists in this tenant",
        ) from exc
    db.refresh(category)
    return category


def get_category(
    db: Session, tenant_id: UUID, category_id: UUID, *, active_only: bool = False
) -> Category:
    query = select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id)
    if active_only:
        query = query.where(Category.is_active.is_(True))
    category = db.scalar(query)
    if category is None:
        raise AppError(404, "CATEGORY_NOT_FOUND", "Category was not found")
    return category


def list_categories(db: Session, tenant_id: UUID, *, include_archived: bool) -> list[Category]:
    query = select(Category).where(Category.tenant_id == tenant_id)
    if not include_archived:
        query = query.where(Category.is_active.is_(True))
    return list(
        db.scalars(
            query.order_by(
                Category.is_active.desc(),
                Category.display_order.asc(),
                Category.name_en.asc(),
                Category.id.asc(),
            )
        )
    )


def update_category(
    db: Session,
    tenant_id: UUID,
    category_id: UUID,
    request: CategoryUpdateRequest,
) -> Category:
    category = get_category(db, tenant_id, category_id)
    if not category.is_active:
        raise AppError(409, "CATEGORY_ARCHIVED", "Archived categories cannot be changed")
    for field_name, value in request.model_dump(exclude_unset=True).items():
        setattr(category, field_name, value)
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "CATEGORY_SLUG_ALREADY_EXISTS",
            "Category slug already exists in this tenant",
        ) from exc
    db.refresh(category)
    return category


def archive_category(db: Session, tenant_id: UUID, category_id: UUID) -> Category:
    category = get_category(db, tenant_id, category_id)
    if not category.is_active:
        return category
    category.is_active = False
    category.archived_at = datetime.now(UTC)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(category)
    return category


def _barcode_sort_key(barcode: MasterBarcode | TenantBarcode) -> tuple[bool, datetime, UUID]:
    return (
        barcode.package_level is BarcodePackageLevel.BOX,
        barcode.created_at,
        barcode.id,
    )


def _master_barcodes(db: Session, master_product_id: UUID) -> list[MasterBarcode]:
    return sorted(
        db.scalars(
            select(MasterBarcode).where(MasterBarcode.master_product_id == master_product_id)
        ),
        key=_barcode_sort_key,
    )


def _tenant_barcodes(db: Session, tenant_id: UUID, tenant_product_id: UUID) -> list[TenantBarcode]:
    return sorted(
        db.scalars(
            select(TenantBarcode).where(
                TenantBarcode.tenant_id == tenant_id,
                TenantBarcode.tenant_product_id == tenant_product_id,
            )
        ),
        key=_barcode_sort_key,
    )


def _barcode_response(
    barcode: MasterBarcode | TenantBarcode, ownership: BarcodeOwnership
) -> BarcodeResponse:
    return BarcodeResponse(
        id=barcode.id,
        barcode=barcode.barcode,
        package_level=barcode.package_level,
        ownership=ownership,
    )


def _image_response(
    image: MasterProductImage | TenantProductImage,
    ownership: MediaOwnership,
    tenant_id: UUID,
) -> ProductImageResponse:
    return ProductImageResponse(
        id=image.id,
        ownership=ownership,
        content_type=image.content_type,
        byte_size=image.byte_size,
        width=image.width,
        height=image.height,
        display_order=image.display_order,
        alt_text=image.alt_text,
        url=(f"/api/v1/tenants/{tenant_id}/product-images/{ownership.value}/{image.id}/content"),
    )


def master_product_response(
    db: Session, tenant_id: UUID, product: MasterProduct
) -> MasterProductResponse:
    return MasterProductResponse(
        id=product.id,
        master_category_id=product.master_category_id,
        name=product.name,
        barcodes=[
            _barcode_response(barcode, BarcodeOwnership.MASTER)
            for barcode in _master_barcodes(db, product.id)
        ],
        images=[
            _image_response(image, MediaOwnership.MASTER, tenant_id)
            for image in list_master_product_images(db, product.id)
        ],
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def product_response(
    db: Session,
    product: TenantProduct,
    *,
    preferred_barcode: str | None = None,
) -> TenantProductResponse:
    piece_price, box_price = derive_counterpart_prices(
        product.unit_price, product.price_basis, product.pieces_per_box
    )
    barcode_responses = [
        _barcode_response(barcode, BarcodeOwnership.TENANT)
        for barcode in _tenant_barcodes(db, product.tenant_id, product.id)
    ]
    if product.master_product_id is not None:
        barcode_responses.extend(
            _barcode_response(barcode, BarcodeOwnership.MASTER)
            for barcode in _master_barcodes(db, product.master_product_id)
        )
    barcode_responses.sort(
        key=lambda item: (
            item.package_level is BarcodePackageLevel.BOX,
            item.ownership is BarcodeOwnership.MASTER,
            str(item.id),
        )
    )
    if not barcode_responses:
        raise RuntimeError("Tenant product is missing a barcode")
    primary_barcode = next(
        (barcode.barcode for barcode in barcode_responses if barcode.barcode == preferred_barcode),
        barcode_responses[0].barcode,
    )
    return TenantProductResponse(
        id=product.id,
        tenant_id=product.tenant_id,
        category_id=product.category_id,
        master_product_id=product.master_product_id,
        name=product.name,
        barcode=primary_barcode,
        barcodes=barcode_responses,
        images=[
            _image_response(image, MediaOwnership.TENANT, product.tenant_id)
            for image in list_tenant_product_images(db, product.tenant_id, product.id)
        ]
        + (
            [
                _image_response(image, MediaOwnership.MASTER, product.tenant_id)
                for image in list_master_product_images(db, product.master_product_id)
            ]
            if product.master_product_id is not None
            else []
        ),
        grade_prices=[
            ProductGradePriceResponse.model_validate(grade_price)
            for grade_price in list_product_grade_prices(db, product.tenant_id, product.id)
        ],
        is_published=product.is_published,
        unit_price=_money(product.unit_price),
        currency=product.currency,
        price_basis=product.price_basis,
        pieces_per_box=product.pieces_per_box,
        piece_price=piece_price,
        box_price=box_price,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def build_product(
    db: Session,
    tenant_id: UUID,
    request: TenantProductCreateRequest,
    *,
    product_id: UUID | None = None,
) -> TenantProduct:
    """Validate and stage a tenant product plus its barcode without committing.

    The sync push path reuses this so the domain rows, the idempotency record and the change
    records commit in one transaction; `create_product` remains the committing API path.
    """
    get_category(db, tenant_id, request.category_id, active_only=True)
    master_product = (
        db.get(MasterProduct, request.master_product_id)
        if request.master_product_id is not None
        else None
    )
    if request.master_product_id is not None and master_product is None:
        raise AppError(404, "MASTER_PRODUCT_NOT_FOUND", "Master product was not found")
    master_barcode = db.scalar(
        select(MasterBarcode).where(MasterBarcode.barcode == request.barcode)
    )
    if master_barcode is not None and request.master_product_id is None:
        raise AppError(
            409,
            "MASTER_PRODUCT_LINK_REQUIRED",
            "Known master barcode must be linked to its master product",
        )
    if master_barcode is not None and master_barcode.master_product_id != request.master_product_id:
        raise AppError(
            409,
            "BARCODE_MASTER_PRODUCT_MISMATCH",
            "Barcode belongs to a different master product",
        )
    existing_barcode = db.scalar(
        select(TenantBarcode.id).where(
            TenantBarcode.tenant_id == tenant_id,
            TenantBarcode.barcode == request.barcode,
        )
    )
    if existing_barcode is not None:
        raise AppError(409, "BARCODE_ALREADY_EXISTS", "Barcode already exists in this tenant")
    if request.master_product_id is not None:
        adopted = db.scalar(
            select(TenantProduct.id).where(
                TenantProduct.tenant_id == tenant_id,
                TenantProduct.master_product_id == request.master_product_id,
            )
        )
        if adopted is not None:
            raise AppError(
                409,
                "MASTER_PRODUCT_ALREADY_ADOPTED",
                "Master product is already linked in this tenant",
            )
    product = TenantProduct(
        tenant_id=tenant_id,
        category_id=request.category_id,
        master_product_id=request.master_product_id,
        name=request.name,
        is_published=request.is_published,
        unit_price=_money(request.unit_price),
        currency=request.currency,
        price_basis=request.price_basis,
        pieces_per_box=request.pieces_per_box,
    )
    if product_id is not None:
        product.id = product_id
    db.add(product)
    db.flush()
    if master_barcode is None:
        db.add(
            TenantBarcode(
                tenant_id=tenant_id,
                tenant_product_id=product.id,
                barcode=request.barcode,
                package_level=request.barcode_package_level,
            )
        )
    return product


def create_product(
    db: Session, tenant_id: UUID, request: TenantProductCreateRequest
) -> TenantProduct:
    product = build_product(db, tenant_id, request)
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409, "BARCODE_ALREADY_EXISTS", "Barcode already exists in this tenant"
        ) from exc
    db.refresh(product)
    return product


def list_products(db: Session, tenant_id: UUID) -> list[TenantProduct]:
    return list(
        db.scalars(
            select(TenantProduct)
            .where(TenantProduct.tenant_id == tenant_id)
            .order_by(TenantProduct.name.asc(), TenantProduct.id.asc())
        )
    )


def update_product(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    request: TenantProductUpdateRequest,
) -> TenantProduct:
    product = get_product(db, tenant_id, product_id)
    values = request.model_dump(exclude_unset=True)
    if "category_id" in values:
        get_category(db, tenant_id, values["category_id"], active_only=True)
    grade_prices = list_product_grade_prices(db, tenant_id, product.id)
    if grade_prices and (
        ("price_basis" in values and values["price_basis"] != product.price_basis)
        or ("currency" in values and values["currency"] != product.currency)
    ):
        raise AppError(
            409,
            "GRADE_PRICES_REQUIRE_RESET",
            "Clear explicit grade prices before changing product currency or price basis",
        )
    final_basis = values.get("price_basis", product.price_basis)
    final_piece_count = values.get("pieces_per_box", product.pieces_per_box)
    if final_basis is ProductPriceBasis.BOX and final_piece_count is None:
        raise AppError(
            400,
            "PIECES_PER_BOX_REQUIRED",
            "pieces_per_box is required when price_basis is BOX",
        )
    for field_name, value in values.items():
        setattr(product, field_name, value)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(product)
    return product


def add_product_barcode(
    db: Session,
    tenant_id: UUID,
    product_id: UUID,
    request: BarcodeCreateRequest,
) -> TenantProduct:
    product = get_product(db, tenant_id, product_id)
    master_barcode = db.scalar(
        select(MasterBarcode).where(MasterBarcode.barcode == request.barcode)
    )
    if master_barcode is not None:
        raise AppError(
            409,
            "BARCODE_OWNED_BY_MASTER",
            "Known master barcode cannot be copied into tenant barcode ownership",
        )
    existing = db.scalar(
        select(TenantBarcode.id).where(
            TenantBarcode.tenant_id == tenant_id,
            TenantBarcode.barcode == request.barcode,
        )
    )
    if existing is not None:
        raise AppError(409, "BARCODE_ALREADY_EXISTS", "Barcode already exists in this tenant")
    db.add(
        TenantBarcode(
            tenant_id=tenant_id,
            tenant_product_id=product.id,
            barcode=request.barcode,
            package_level=request.package_level,
        )
    )
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
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


def lookup_barcode(db: Session, tenant_id: UUID, barcode: str) -> BarcodeLookupResponse:
    normalized = barcode.strip()
    tenant_barcode = db.scalar(
        select(TenantBarcode).where(
            TenantBarcode.tenant_id == tenant_id,
            TenantBarcode.barcode == normalized,
        )
    )
    if tenant_barcode is not None:
        product = get_product(db, tenant_id, tenant_barcode.tenant_product_id)
        master_product = (
            db.get(MasterProduct, product.master_product_id)
            if product.master_product_id is not None
            else None
        )
        return BarcodeLookupResponse(
            barcode=normalized,
            ownership=BarcodeOwnership.TENANT,
            package_level=tenant_barcode.package_level,
            master_product=(
                master_product_response(db, tenant_id, master_product)
                if master_product is not None
                else None
            ),
            tenant_product=product_response(db, product, preferred_barcode=normalized),
        )

    master_barcode = db.scalar(select(MasterBarcode).where(MasterBarcode.barcode == normalized))
    if master_barcode is None:
        raise AppError(404, "BARCODE_NOT_FOUND", "Barcode was not found")
    master_product = db.get(MasterProduct, master_barcode.master_product_id)
    if master_product is None:
        raise RuntimeError("Master barcode is missing its product")
    tenant_product = db.scalar(
        select(TenantProduct).where(
            TenantProduct.tenant_id == tenant_id,
            TenantProduct.master_product_id == master_product.id,
        )
    )
    return BarcodeLookupResponse(
        barcode=normalized,
        ownership=BarcodeOwnership.MASTER,
        package_level=master_barcode.package_level,
        master_product=master_product_response(db, tenant_id, master_product),
        tenant_product=(
            product_response(db, tenant_product, preferred_barcode=normalized)
            if tenant_product is not None
            else None
        ),
    )


def get_product_by_barcode(db: Session, tenant_id: UUID, barcode: str) -> tuple[TenantProduct, str]:
    result = lookup_barcode(db, tenant_id, barcode)
    if result.tenant_product is None:
        raise AppError(404, "PRODUCT_NOT_FOUND", "Tenant product was not found")
    return get_product(db, tenant_id, result.tenant_product.id), result.barcode


def _invoice_response(db: Session, tenant_id: UUID, invoice: Invoice) -> DraftInvoiceResponse:
    revision = db.scalar(
        select(InvoiceRevision).where(
            InvoiceRevision.id == invoice.current_revision_id,
            InvoiceRevision.invoice_id == invoice.id,
            InvoiceRevision.tenant_id == tenant_id,
        )
    )
    if revision is None:
        raise AppError(409, "INVOICE_REVISION_MISSING", "Invoice revision was not found")
    if invoice.customer_id is None:
        raise AppError(409, "INVOICE_CUSTOMER_MISSING", "Draft invoice customer was not found")
    customer = get_customer(db, tenant_id, invoice.customer_id)
    items = list(
        db.scalars(
            select(InvoiceRevisionItem)
            .where(
                InvoiceRevisionItem.invoice_revision_id == revision.id,
                InvoiceRevisionItem.tenant_id == tenant_id,
            )
            .order_by(InvoiceRevisionItem.line_number.asc())
        )
    )
    return DraftInvoiceResponse(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        customer=CustomerResponse.model_validate(customer),
        status=invoice.status,
        currency=revision.currency,
        subtotal=revision.subtotal,
        items=[
            InvoiceItemResponse(
                id=item.id,
                product_id=item.tenant_product_id,
                product_name=item.product_name,
                barcode=item.barcode or "",
                quantity=item.quantity,
                price_basis=item.price_basis,
                unit_price=item.effective_unit_price,
                line_total=item.line_total,
                customer_grade=item.customer_grade,
                price_source=item.price_source,
                grade_discount_percent=item.grade_discount_percent,
            )
            for item in items
            if item.tenant_product_id is not None
        ],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def create_draft_invoice(
    db: Session, tenant_id: UUID, request: DraftInvoiceCreateRequest
) -> DraftInvoiceResponse:
    customer = get_customer(db, tenant_id, request.customer_id)
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
    prepared_items: list[
        tuple[TenantProduct, DraftInvoiceItemCreateRequest, Decimal, str, dict[str, object]]
    ] = []
    subtotal = Decimal("0.0000")
    for requested_item in request.items:
        product = products_by_id[requested_item.product_id]
        pricing = resolve_product_pricing(db, tenant_id, product, customer.grade)
        line_total = _money(pricing.basis_price * requested_item.quantity)
        subtotal += line_total
        response = product_response(db, product)
        prepared_items.append(
            (
                product,
                requested_item,
                line_total,
                response.barcode,
                {"images": [image.model_dump(mode="json") for image in response.images]},
            )
        )

    # D-037: the due snapshot is prior balance plus net sales at the time the revision is saved,
    # exactly as the production editor computes it; the legacy route must not hardcode zero.
    prior_balance = _money(
        Decimal(
            db.scalar(
                select(func.coalesce(func.sum(CustomerLedgerEntry.signed_amount), 0)).where(
                    CustomerLedgerEntry.tenant_id == tenant_id,
                    CustomerLedgerEntry.customer_id == customer.id,
                    CustomerLedgerEntry.currency == currency,
                )
            )
            or 0
        )
    )
    invoice_id = uuid4()
    revision_id = uuid4()
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant_id,
        customer_id=request.customer_id,
        status=InvoiceStatus.DRAFT,
        current_revision_id=revision_id,
    )
    db.add(invoice)
    db.flush()
    revision = InvoiceRevision(
        id=revision_id,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        client_command_id=uuid4(),
        server_revision_number=1,
        pricing_version="pricing-v1",
        currency=currency,
        customer_id=customer.id,
        customer_snapshot={
            "id": str(customer.id),
            "name": customer.name,
            "phone": customer.phone,
            "address": customer.address,
            "grade": str(customer.grade) if customer.grade is not None else None,
        },
        prior_balance_snapshot=prior_balance,
        subtotal=_money(subtotal),
        discount_total=Decimal("0.0000"),
        markup_total=Decimal("0.0000"),
        net_sales=_money(subtotal),
        amount_due_display=_money(prior_balance + subtotal),
    )
    db.add(revision)
    for line_number, (
        product,
        requested_item,
        line_total,
        barcode,
        media_snapshot,
    ) in enumerate(prepared_items, start=1):
        pricing = resolve_product_pricing(db, tenant_id, product, customer.grade)
        db.add(
            InvoiceRevisionItem(
                tenant_id=tenant_id,
                invoice_revision_id=revision_id,
                line_number=line_number,
                tenant_product_id=product.id,
                product_name=product.name,
                barcode=barcode,
                media_snapshot=media_snapshot,
                quantity=requested_item.quantity,
                price_basis=product.price_basis,
                pieces_per_box=product.pieces_per_box,
                normal_unit_price=product.unit_price,
                grade_rule_snapshot={
                    "customer_grade": (str(customer.grade) if customer.grade is not None else None),
                    "price_source": str(pricing.source),
                    "discount_percent": (
                        str(pricing.discount_percent)
                        if pricing.discount_percent is not None
                        else None
                    ),
                },
                effective_unit_price=pricing.basis_price,
                line_discount=Decimal("0.0000"),
                line_markup=Decimal("0.0000"),
                line_total=line_total,
                customer_grade=customer.grade,
                price_source=pricing.source,
                grade_discount_percent=pricing.discount_percent,
            )
        )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(invoice)
    return _invoice_response(db, tenant_id, invoice)


def get_draft_invoice(db: Session, tenant_id: UUID, invoice_id: UUID) -> DraftInvoiceResponse:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    )
    if invoice is None:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    return _invoice_response(db, tenant_id, invoice)
