from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, get_current_user, require_tenant_owner
from tawzeevo_api.models import CustomerGrade, MediaOwnership, User
from tawzeevo_api.schemas.cash_van import (
    BarcodeCreateRequest,
    BarcodeLookupResponse,
    CategoryCreateRequest,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdateRequest,
    CustomerCreateRequest,
    CustomerResponse,
    CustomerSearchResponse,
    CustomerUpdateRequest,
    DraftInvoiceCreateRequest,
    DraftInvoiceResponse,
    GradeDiscountListResponse,
    GradeDiscountRequest,
    GradeDiscountResponse,
    ProductGradePriceRequest,
    ProductGradePriceResponse,
    ProductImageResponse,
    ResolvedProductPriceResponse,
    TenantContextListResponse,
    TenantContextResponse,
    TenantProductCreateRequest,
    TenantProductListResponse,
    TenantProductResponse,
    TenantProductUpdateRequest,
)
from tawzeevo_api.services.cash_van import (
    add_product_barcode,
    archive_category,
    create_category,
    create_customer,
    create_draft_invoice,
    create_product,
    get_category,
    get_customer,
    get_draft_invoice,
    get_product,
    get_product_by_barcode,
    list_categories,
    list_products,
    lookup_barcode,
    product_response,
    search_customers_by_phone,
    update_category,
    update_customer,
    update_product,
)
from tawzeevo_api.services.media import (
    ObjectStorage,
    get_master_image_content,
    get_object_storage,
    get_tenant_image_content,
    process_product_image,
    upload_tenant_product_image,
)
from tawzeevo_api.services.memberships import list_user_tenant_contexts
from tawzeevo_api.services.pricing import (
    clear_grade_discount,
    clear_product_grade_price,
    list_grade_discounts,
    resolve_product_pricing,
    set_grade_discount,
    set_product_grade_price,
)

cash_van_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["tenant operations"])
tenant_contexts_router = APIRouter(prefix="/api/v1", tags=["tenant operations"])


def _storage_dependency() -> ObjectStorage:
    return get_object_storage()


@tenant_contexts_router.get("/tenant-contexts", response_model=TenantContextListResponse)
def user_tenant_contexts(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TenantContextListResponse:
    contexts = list_user_tenant_contexts(db, user.id)
    return TenantContextListResponse(
        tenants=[
            TenantContextResponse(
                membership_id=membership.id,
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                tenant_status=tenant.status,
                role=membership.role,
            )
            for membership, tenant in contexts
        ]
    )


@cash_van_router.post(
    "/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED
)
def tenant_create_customer(
    request: CustomerCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerResponse:
    return CustomerResponse.model_validate(create_customer(db, context.tenant.id, request))


@cash_van_router.get("/customers/search", response_model=CustomerSearchResponse)
def tenant_search_customers(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    phone: Annotated[str, Query(min_length=1, max_length=64)],
) -> CustomerSearchResponse:
    customers = search_customers_by_phone(db, context.tenant.id, phone)
    return CustomerSearchResponse(
        customers=[CustomerResponse.model_validate(customer) for customer in customers]
    )


@cash_van_router.get("/customers/{customer_id}", response_model=CustomerResponse)
def tenant_get_customer(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerResponse:
    return CustomerResponse.model_validate(get_customer(db, context.tenant.id, customer_id))


@cash_van_router.put("/customers/{customer_id}", response_model=CustomerResponse)
def tenant_update_customer(
    customer_id: UUID,
    request: CustomerUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerResponse:
    return CustomerResponse.model_validate(
        update_customer(db, context.tenant.id, customer_id, request)
    )


@cash_van_router.post(
    "/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
def tenant_create_category(
    request: CategoryCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CategoryResponse:
    return CategoryResponse.model_validate(create_category(db, context.tenant.id, request))


@cash_van_router.get("/categories", response_model=CategoryListResponse)
def tenant_list_categories(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    include_archived: bool = False,
) -> CategoryListResponse:
    categories = list_categories(db, context.tenant.id, include_archived=include_archived)
    return CategoryListResponse(
        categories=[CategoryResponse.model_validate(category) for category in categories]
    )


@cash_van_router.get("/categories/{category_id}", response_model=CategoryResponse)
def tenant_get_category(
    category_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CategoryResponse:
    return CategoryResponse.model_validate(get_category(db, context.tenant.id, category_id))


@cash_van_router.put("/categories/{category_id}", response_model=CategoryResponse)
def tenant_update_category(
    category_id: UUID,
    request: CategoryUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CategoryResponse:
    return CategoryResponse.model_validate(
        update_category(db, context.tenant.id, category_id, request)
    )


@cash_van_router.post("/categories/{category_id}/archive", response_model=CategoryResponse)
def tenant_archive_category(
    category_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CategoryResponse:
    return CategoryResponse.model_validate(archive_category(db, context.tenant.id, category_id))


@cash_van_router.post(
    "/products", response_model=TenantProductResponse, status_code=status.HTTP_201_CREATED
)
def tenant_create_product(
    request: TenantProductCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(db, create_product(db, context.tenant.id, request))


@cash_van_router.get("/products", response_model=TenantProductListResponse)
def tenant_list_products(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductListResponse:
    return TenantProductListResponse(
        products=[product_response(db, product) for product in list_products(db, context.tenant.id)]
    )


@cash_van_router.get("/grade-discounts", response_model=GradeDiscountListResponse)
def tenant_list_grade_discounts(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> GradeDiscountListResponse:
    return GradeDiscountListResponse(
        discounts=[
            GradeDiscountResponse.model_validate(discount)
            for discount in list_grade_discounts(db, context.tenant.id)
        ]
    )


@cash_van_router.put("/grade-discounts/{grade}", response_model=GradeDiscountResponse)
def tenant_set_grade_discount(
    grade: CustomerGrade,
    request: GradeDiscountRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> GradeDiscountResponse:
    return GradeDiscountResponse.model_validate(
        set_grade_discount(db, context.tenant.id, grade, request.discount_percent)
    )


@cash_van_router.delete("/grade-discounts/{grade}", status_code=status.HTTP_204_NO_CONTENT)
def tenant_clear_grade_discount(
    grade: CustomerGrade,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> Response:
    clear_grade_discount(db, context.tenant.id, grade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@cash_van_router.get("/catalog/barcodes/{barcode}", response_model=BarcodeLookupResponse)
def tenant_lookup_catalog_barcode(
    barcode: str,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> BarcodeLookupResponse:
    return lookup_barcode(db, context.tenant.id, barcode)


@cash_van_router.get("/products/barcode/{barcode}", response_model=TenantProductResponse)
def tenant_get_product_by_barcode(
    barcode: str,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    product, resolved_barcode = get_product_by_barcode(db, context.tenant.id, barcode)
    return product_response(db, product, preferred_barcode=resolved_barcode)


@cash_van_router.get("/products/{product_id}", response_model=TenantProductResponse)
def tenant_get_product(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(db, get_product(db, context.tenant.id, product_id))


@cash_van_router.get("/products/{product_id}/pricing", response_model=ResolvedProductPriceResponse)
def tenant_resolve_product_pricing(
    product_id: UUID,
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ResolvedProductPriceResponse:
    product = get_product(db, context.tenant.id, product_id)
    customer = get_customer(db, context.tenant.id, customer_id)
    pricing = resolve_product_pricing(db, context.tenant.id, product, customer.grade)
    return ResolvedProductPriceResponse(
        product_id=product.id,
        customer_id=customer.id,
        customer_grade=pricing.customer_grade,
        source=pricing.source,
        discount_percent=pricing.discount_percent,
        currency=product.currency,
        price_basis=product.price_basis,
        basis_price=pricing.basis_price,
        piece_price=pricing.piece_price,
        box_price=pricing.box_price,
    )


@cash_van_router.put(
    "/products/{product_id}/grade-prices/{grade}",
    response_model=ProductGradePriceResponse,
)
def tenant_set_product_grade_price(
    product_id: UUID,
    grade: CustomerGrade,
    request: ProductGradePriceRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ProductGradePriceResponse:
    get_product(db, context.tenant.id, product_id)
    return ProductGradePriceResponse.model_validate(
        set_product_grade_price(db, context.tenant.id, product_id, grade, request.unit_price)
    )


@cash_van_router.delete(
    "/products/{product_id}/grade-prices/{grade}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def tenant_clear_product_grade_price(
    product_id: UUID,
    grade: CustomerGrade,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> Response:
    get_product(db, context.tenant.id, product_id)
    clear_product_grade_price(db, context.tenant.id, product_id, grade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@cash_van_router.post(
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def tenant_upload_product_image(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    storage: Annotated[ObjectStorage, Depends(_storage_dependency)],
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str | None, Form(max_length=300)] = None,
    display_order: Annotated[int, Form(ge=0)] = 0,
) -> ProductImageResponse:
    settings = get_settings()
    content = await file.read(settings.media_max_upload_bytes + 1)
    processed = process_product_image(content, file.content_type)
    image = upload_tenant_product_image(
        db,
        storage,
        context.tenant.id,
        product_id,
        processed,
        alt_text=alt_text,
        display_order=display_order,
    )
    product = product_response(db, get_product(db, context.tenant.id, product_id))
    return next(response for response in product.images if response.id == image.id)


@cash_van_router.get("/product-images/{ownership}/{image_id}/content")
def tenant_get_product_image_content(
    ownership: MediaOwnership,
    image_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    storage: Annotated[ObjectStorage, Depends(_storage_dependency)],
) -> Response:
    if ownership is MediaOwnership.TENANT:
        tenant_image, content = get_tenant_image_content(db, storage, context.tenant.id, image_id)
        content_type = tenant_image.content_type
    else:
        master_image, content = get_master_image_content(db, storage, image_id)
        content_type = master_image.content_type
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@cash_van_router.put("/products/{product_id}", response_model=TenantProductResponse)
def tenant_update_product(
    product_id: UUID,
    request: TenantProductUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(
        db,
        update_product(db, context.tenant.id, product_id, request),
    )


@cash_van_router.post(
    "/products/{product_id}/barcodes",
    response_model=TenantProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def tenant_add_product_barcode(
    product_id: UUID,
    request: BarcodeCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(
        db,
        add_product_barcode(db, context.tenant.id, product_id, request),
        preferred_barcode=request.barcode,
    )


@cash_van_router.post(
    "/invoices", response_model=DraftInvoiceResponse, status_code=status.HTTP_201_CREATED
)
def tenant_create_draft_invoice(
    request: DraftInvoiceCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> DraftInvoiceResponse:
    return create_draft_invoice(db, context.tenant.id, request)


@cash_van_router.get("/invoices/{invoice_id}", response_model=DraftInvoiceResponse)
def tenant_get_draft_invoice(
    invoice_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> DraftInvoiceResponse:
    return get_draft_invoice(db, context.tenant.id, invoice_id)
