from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.errors import AppError
from tawzeevo_api.routes.cash_van import _storage_dependency
from tawzeevo_api.schemas.storefront import (
    CampaignListResponse,
    CampaignRequest,
    CampaignResponse,
    FeaturedResponse,
    PublicProduct,
    PublicProductPage,
    PublicStorefront,
    StorefrontSettings,
    StorefrontSlugRequest,
    ViewRequest,
    ViewResponse,
)
from tawzeevo_api.services import storefront, storefront_signals
from tawzeevo_api.services.media import ObjectStorage

storefront_public_router = APIRouter(prefix="/api/v1/public", tags=["storefront"])
storefront_owner_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["storefront"])

# Public catalog pages are shareable and cacheable for a short time; they hold no private data.
PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"


@storefront_public_router.get("/{tenant_slug}/catalog", response_model=PublicStorefront)
def read_storefront(
    tenant_slug: str, response: Response, db: Annotated[Session, Depends(get_db)]
) -> PublicStorefront:
    """The business card and its categories; `redirected_from` is set after a rename."""
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return storefront.public_storefront(db, tenant_slug)


@storefront_public_router.get("/{tenant_slug}/catalog/products", response_model=PublicProductPage)
def read_products(
    tenant_slug: str,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[str | None, Query(max_length=120)] = None,
    category_id: UUID | None = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=storefront.MAX_PAGE_SIZE)] = storefront.PAGE_SIZE,
) -> PublicProductPage:
    """Published products only, exact/prefix-first, bounded and paginated."""
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return storefront.public_products(
        db, tenant_slug, query=query, category_id=category_id, page=page, page_size=page_size
    )


@storefront_public_router.get(
    "/{tenant_slug}/catalog/products/{product_id}", response_model=PublicProduct
)
def read_product(
    tenant_slug: str,
    product_id: UUID,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> PublicProduct:
    response.headers["Cache-Control"] = PUBLIC_CACHE
    return storefront.public_product(db, tenant_slug, product_id)


@storefront_public_router.get("/{tenant_slug}/catalog/images/{kind}/{image_id}")
def read_image(
    tenant_slug: str,
    kind: Literal["tenant", "master"],
    image_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[ObjectStorage, Depends(_storage_dependency)],
) -> Response:
    located = storefront.public_image(db, tenant_slug, kind, image_id)
    if located is None:
        raise AppError(404, "PRODUCT_IMAGE_NOT_FOUND", "Product image was not found")
    object_key, content_type = located
    return Response(
        content=storage.get_bytes(object_key),
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@storefront_owner_router.get("/storefront", response_model=StorefrontSettings)
def read_storefront_settings(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> StorefrontSettings:
    return storefront.storefront_settings(db, context.tenant)


@storefront_owner_router.put("/storefront/slug", response_model=StorefrontSettings)
def rename_storefront_slug(
    request: StorefrontSlugRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> StorefrontSettings:
    """Audited rename (D-047); the previous address keeps redirecting."""
    return storefront.rename_slug(db, context.tenant, context.membership.user_id, request.slug)


@storefront_public_router.get("/{tenant_slug}/catalog/featured", response_model=FeaturedResponse)
def read_featured(
    tenant_slug: str, response: Response, db: Annotated[Session, Depends(get_db)]
) -> FeaturedResponse:
    """Active owner campaigns (priority, newer, id); unpublished products are silently absent."""
    response.headers["Cache-Control"] = PUBLIC_CACHE
    tenant_id = storefront.public_tenant_id(db, tenant_slug)
    ids = storefront_signals.active_featured_product_ids(db, tenant_id)
    return FeaturedResponse(items=storefront.public_products_by_ids(db, tenant_slug, ids))


@storefront_public_router.get("/{tenant_slug}/catalog/recommended", response_model=FeaturedResponse)
def read_recommended(
    tenant_slug: str,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> FeaturedResponse:
    """Deterministic ranking: valid purchases weigh 10, pseudonymous views 1 (D-048)."""
    response.headers["Cache-Control"] = PUBLIC_CACHE
    tenant_id = storefront.public_tenant_id(db, tenant_slug)
    ids = storefront_signals.ranked_product_ids(db, tenant_id, limit)
    return FeaturedResponse(items=storefront.public_products_by_ids(db, tenant_slug, ids))


@storefront_public_router.post(
    "/{tenant_slug}/catalog/products/{product_id}/view", response_model=ViewResponse
)
def record_product_view(
    tenant_slug: str,
    product_id: UUID,
    request: ViewRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> ViewResponse:
    """One pseudonymous view per session and product per 30 minutes (D-062)."""
    response.headers["Cache-Control"] = "no-store"
    tenant_id = storefront.public_tenant_id(db, tenant_slug)
    return ViewResponse(
        counted=storefront_signals.record_view(db, tenant_id, product_id, request.session_id)
    )


def _campaign(row: object) -> CampaignResponse:
    result = CampaignResponse.model_validate(row)
    now = datetime.now(UTC)
    result.active = result.cancelled_at is None and result.starts_at <= now < result.ends_at
    return result


@storefront_owner_router.get("/storefront/campaigns", response_model=CampaignListResponse)
def list_campaigns(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CampaignListResponse:
    rows = storefront_signals.list_campaigns(db, context.tenant.id)
    return CampaignListResponse(campaigns=[_campaign(row) for row in rows])


@storefront_owner_router.post(
    "/storefront/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED
)
def create_campaign(
    request: CampaignRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CampaignResponse:
    """Feature one of this business's products; 7 days by default (PHASE_05.md K)."""
    row = storefront_signals.create_campaign(
        db,
        context.tenant,
        context.membership.user_id,
        request.product_id,
        request.starts_at,
        request.ends_at,
        request.priority,
    )
    return _campaign(row)


@storefront_owner_router.post(
    "/storefront/campaigns/{campaign_id}/cancel", response_model=CampaignResponse
)
def cancel_campaign(
    campaign_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CampaignResponse:
    row = storefront_signals.cancel_campaign(
        db, context.tenant.id, context.membership.user_id, campaign_id
    )
    return _campaign(row)
