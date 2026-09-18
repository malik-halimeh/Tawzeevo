from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.errors import AppError
from tawzeevo_api.routes.cash_van import _storage_dependency
from tawzeevo_api.schemas.storefront import (
    PublicProduct,
    PublicProductPage,
    PublicStorefront,
    StorefrontSettings,
    StorefrontSlugRequest,
)
from tawzeevo_api.services import storefront
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
