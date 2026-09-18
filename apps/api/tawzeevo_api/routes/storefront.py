from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.errors import AppError
from tawzeevo_api.routes.cash_van import _storage_dependency
from tawzeevo_api.schemas.storefront import (
    CampaignListResponse,
    CampaignRequest,
    CampaignResponse,
    CustomerContextResponse,
    CustomerLinkResponse,
    CustomerLinkStatusResponse,
    CustomerPolicyRequest,
    FeaturedResponse,
    IssuedCustomerLinkResponse,
    PublicProduct,
    PublicProductPage,
    PublicStorefront,
    StorefrontSettings,
    StorefrontSlugRequest,
    TenantPolicyRequest,
    ViewRequest,
    ViewResponse,
)
from tawzeevo_api.services import customer_access, storefront, storefront_signals
from tawzeevo_api.services.media import ObjectStorage

storefront_public_router = APIRouter(prefix="/api/v1/public", tags=["storefront"])
storefront_owner_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["storefront"])

# Public catalog pages are shareable and cacheable for a short time; they hold no private data.
PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"
# A personalized response is for one visitor only (D-075).
PRIVATE_CACHE = "private, no-store"
CAPABILITY_HEADER = "X-Customer-Capability"


def _context(
    db: Session, request: Request, response: Response
) -> customer_access.CustomerContext | None:
    """Optional personalization: a valid capability in the private header personalizes prices;
    anything else (absent, revoked, rotated, suspended business) is simply anonymous."""
    context = customer_access.resolve_context(db, request.headers.get(CAPABILITY_HEADER))
    response.headers["Cache-Control"] = PRIVATE_CACHE if context else PUBLIC_CACHE
    response.headers["Vary"] = CAPABILITY_HEADER
    return context


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
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    query: Annotated[str | None, Query(max_length=120)] = None,
    category_id: UUID | None = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=storefront.MAX_PAGE_SIZE)] = storefront.PAGE_SIZE,
) -> PublicProductPage:
    """Published products only, exact/prefix-first, bounded and paginated; personalized prices
    with a valid customer capability header."""
    context = _context(db, request, response)
    return storefront.public_products(
        db,
        tenant_slug,
        query=query,
        category_id=category_id,
        page=page,
        page_size=page_size,
        context=context,
    )


@storefront_public_router.get(
    "/{tenant_slug}/catalog/products/{product_id}", response_model=PublicProduct
)
def read_product(
    tenant_slug: str,
    product_id: UUID,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> PublicProduct:
    context = _context(db, request, response)
    return storefront.public_product(db, tenant_slug, product_id, context)


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
    tenant_slug: str,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> FeaturedResponse:
    """Active owner campaigns (priority, newer, id); unpublished products are silently absent."""
    context = _context(db, request, response)
    tenant_id = storefront.public_tenant_id(db, tenant_slug)
    ids = storefront_signals.active_featured_product_ids(db, tenant_id)
    return FeaturedResponse(items=storefront.public_products_by_ids(db, tenant_slug, ids, context))


@storefront_public_router.get("/{tenant_slug}/catalog/recommended", response_model=FeaturedResponse)
def read_recommended(
    tenant_slug: str,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> FeaturedResponse:
    """Deterministic ranking: valid purchases weigh 10, pseudonymous views 1 (D-048)."""
    context = _context(db, request, response)
    tenant_id = storefront.public_tenant_id(db, tenant_slug)
    ids = storefront_signals.ranked_product_ids(db, tenant_id, limit)
    return FeaturedResponse(items=storefront.public_products_by_ids(db, tenant_slug, ids, context))


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


# ---------------------------------------------------------------------------------------------
# Personalized customer context (P5-M3; D-071, D-072, D-075)
# ---------------------------------------------------------------------------------------------


@storefront_public_router.get("/customer-context", response_model=CustomerContextResponse)
def read_customer_context(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
) -> CustomerContextResponse:
    """Fixed path; the capability travels only in the private header. Answers with the least
    the storefront needs (assurance, business, display name) or a constant 404."""
    response.headers["Cache-Control"] = PRIVATE_CACHE
    context = customer_access.require_context(db, capability)
    return CustomerContextResponse(
        assurance=context.assurance.value,
        tenant_slug=context.tenant_slug,
        display_name=context.display_name,
    )


def _status(db: Session, context: TenantContext, customer_id: UUID) -> CustomerLinkStatusResponse:
    from tawzeevo_api.services.cash_van import get_customer

    customer = get_customer(db, context.tenant.id, customer_id)
    active = customer_access.link_status(db, context.tenant.id, customer_id)
    return CustomerLinkStatusResponse(
        active=CustomerLinkResponse.model_validate(active) if active else None,
        effective_policy=customer_access.effective_policy(context.tenant, customer).value,
        policy_override=customer.access_policy_override,
        tenant_policy=context.tenant.customer_access_policy,
        available_policies=[policy.value for policy in customer_access.AVAILABLE_POLICIES],
    )


@storefront_owner_router.get(
    "/customers/{customer_id}/access-link", response_model=CustomerLinkStatusResponse
)
def read_customer_link(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerLinkStatusResponse:
    return _status(db, context, customer_id)


@storefront_owner_router.post(
    "/customers/{customer_id}/access-link",
    response_model=IssuedCustomerLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_customer_link(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> IssuedCustomerLinkResponse:
    """Issue or rotate: the previous link stops working the moment the new one exists."""
    link, raw = customer_access.issue_link(
        db, context.tenant.id, context.membership.user_id, customer_id
    )
    return IssuedCustomerLinkResponse(
        **CustomerLinkResponse.model_validate(link).model_dump(),
        storefront_path=f"/{context.tenant.slug}{customer_access.PUBLIC_ENTRY_PATH}#{raw}",
    )


@storefront_owner_router.delete(
    "/customers/{customer_id}/access-link", response_model=CustomerLinkResponse
)
def revoke_customer_link(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerLinkResponse:
    link = customer_access.revoke_link(
        db, context.tenant.id, context.membership.user_id, customer_id
    )
    return CustomerLinkResponse.model_validate(link)


@storefront_owner_router.put(
    "/customers/{customer_id}/access-policy", response_model=CustomerLinkStatusResponse
)
def set_customer_access_policy(
    customer_id: UUID,
    request: CustomerPolicyRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerLinkStatusResponse:
    customer_access.set_customer_policy(
        db, context.tenant.id, context.membership.user_id, customer_id, request.override
    )
    return _status(db, context, customer_id)


@storefront_owner_router.put("/storefront/access-policy", response_model=StorefrontSettings)
def set_tenant_access_policy(
    request: TenantPolicyRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> StorefrontSettings:
    customer_access.set_tenant_policy(
        db, context.tenant, context.membership.user_id, request.policy
    )
    return storefront.storefront_settings(db, context.tenant)
