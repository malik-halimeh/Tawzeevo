from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.models import ProductPriceBasis
from tawzeevo_api.schemas.suppliers import (
    PreferredSupplierRequest,
    ProductCostEntryCreateRequest,
    ProductCostSetupResponse,
    ProductPriceInsightsResponse,
    SupplierCreateRequest,
    SupplierListResponse,
    SupplierRecommendationResponse,
    SupplierResponse,
    SupplierUpdateRequest,
)
from tawzeevo_api.services.suppliers import (
    append_product_cost,
    create_supplier,
    list_suppliers,
    product_cost_setup,
    product_price_insights,
    recommend_supplier,
    set_preferred_supplier,
    update_supplier,
)

suppliers_router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])
supplier_prices_router = APIRouter(prefix="/api/v1/supplier-prices", tags=["suppliers"])


@supplier_prices_router.get("/products/{product_id}", response_model=ProductPriceInsightsResponse)
def get_product_price_insights(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ProductPriceInsightsResponse:
    """Derived last/low/high/trend/stability per supplier and comparable group (PHASE_06.md C)."""
    return product_price_insights(db, context.tenant.id, product_id)


@supplier_prices_router.get(
    "/products/{product_id}/recommendation", response_model=SupplierRecommendationResponse
)
def get_supplier_recommendation(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    cost_basis: Annotated[ProductPriceBasis | None, Query()] = None,
    pieces_per_box: Annotated[int | None, Query(gt=0)] = None,
) -> SupplierRecommendationResponse:
    """Deterministic comparable ranking with the owner's override (PHASE_06.md D)."""
    return recommend_supplier(db, context.tenant.id, product_id, cost_basis, pieces_per_box)


@suppliers_router.get("", response_model=SupplierListResponse)
def get_suppliers(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierListResponse:
    return list_suppliers(db, context.tenant.id)


@suppliers_router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def post_supplier(
    request: SupplierCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierResponse:
    return create_supplier(db, context.tenant.id, context.membership.user_id, request)


@suppliers_router.patch("/{supplier_id}", response_model=SupplierResponse)
def patch_supplier(
    supplier_id: UUID,
    request: SupplierUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> SupplierResponse:
    return update_supplier(db, context.tenant.id, context.membership.user_id, supplier_id, request)


@suppliers_router.get("/products/{product_id}/costs", response_model=ProductCostSetupResponse)
def get_product_costs(
    product_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ProductCostSetupResponse:
    return product_cost_setup(db, context.tenant.id, product_id)


@suppliers_router.post(
    "/products/{product_id}/costs",
    response_model=ProductCostSetupResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_product_cost(
    product_id: UUID,
    request: ProductCostEntryCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ProductCostSetupResponse:
    return append_product_cost(
        db, context.tenant.id, context.membership.user_id, product_id, request
    )


@suppliers_router.put(
    "/products/{product_id}/preferred-supplier", response_model=ProductCostSetupResponse
)
def put_preferred_supplier(
    product_id: UUID,
    request: PreferredSupplierRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> ProductCostSetupResponse:
    return set_preferred_supplier(
        db, context.tenant.id, context.membership.user_id, product_id, request
    )
