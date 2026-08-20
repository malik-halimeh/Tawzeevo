from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.cash_van import (
    CategoryCreateRequest,
    CategoryListResponse,
    CategoryResponse,
    CustomerCreateRequest,
    CustomerResponse,
    CustomerSearchResponse,
    DraftInvoiceCreateRequest,
    DraftInvoiceResponse,
    TenantProductCreateRequest,
    TenantProductResponse,
)
from tawzeevo_api.services.cash_van import (
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
    product_response,
    search_customers_by_phone,
)

cash_van_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["tenant operations"])


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
) -> CategoryListResponse:
    categories = list_categories(db, context.tenant.id)
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


@cash_van_router.post(
    "/products", response_model=TenantProductResponse, status_code=status.HTTP_201_CREATED
)
def tenant_create_product(
    request: TenantProductCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(create_product(db, context.tenant.id, request))


@cash_van_router.get("/products/barcode/{barcode}", response_model=TenantProductResponse)
def tenant_get_product_by_barcode(
    barcode: str,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(get_product_by_barcode(db, context.tenant.id, barcode))


@cash_van_router.get("/products/{product_id}", response_model=TenantProductResponse)
def tenant_get_product(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> TenantProductResponse:
    return product_response(get_product(db, context.tenant.id, product_id))


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
