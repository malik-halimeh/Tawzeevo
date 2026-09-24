from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import AuditEvent, Customer, DeliveryTask
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.routes.cash_van import _storage_dependency
from tawzeevo_api.schemas.cash_van import CustomerCreateRequest
from tawzeevo_api.schemas.checkout import (
    CancellationDecisionRequest,
    CancellationRequestBody,
    CancellationRequestResponse,
    CheckoutRequest,
    CheckoutResponse,
    ConfirmOrderRequest,
    CustomerCandidate,
    DeclineOrderRequest,
    DeliveryDateRequest,
    LinkCustomerRequest,
    NotificationListResponse,
    NotificationResponse,
    OrderDeliveryRef,
    OrderDetailResponse,
    OrderListResponse,
    OrderSummary,
    ProvisionalOrderResponse,
)
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
    VerificationConfirmRequest,
    VerificationSessionResponse,
    ViewRequest,
    ViewResponse,
)
from tawzeevo_api.services import (
    branding,
    checkout,
    customer_access,
    customer_verification,
    orders,
    storefront,
    storefront_signals,
)
from tawzeevo_api.services.media import ObjectStorage
from tawzeevo_api.services.otp_delivery import dev_delivery

storefront_public_router = APIRouter(prefix="/api/v1/public", tags=["storefront"])
storefront_owner_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["storefront"])

# Public catalog pages are shareable and cacheable for a short time; they hold no private data.
PUBLIC_CACHE = "public, max-age=60, stale-while-revalidate=300"
# A personalized response is for one visitor only (D-075).
PRIVATE_CACHE = "private, no-store"
CAPABILITY_HEADER = "X-Customer-Capability"
SESSION_HEADER = customer_access.SESSION_HEADER


def _context(
    db: Session, request: Request, response: Response
) -> customer_access.CustomerContext | None:
    """Optional personalization: a valid capability in the private header personalizes prices;
    anything else (absent, revoked, rotated, suspended business) is simply anonymous."""
    context = customer_access.resolve_context(
        db, request.headers.get(CAPABILITY_HEADER), request.headers.get(SESSION_HEADER)
    )
    response.headers["Cache-Control"] = PRIVATE_CACHE if context else PUBLIC_CACHE
    response.headers["Vary"] = f"{CAPABILITY_HEADER}, {SESSION_HEADER}"
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


@storefront_public_router.get("/{tenant_slug}/branding/logo")
def read_logo(tenant_slug: str, db: Annotated[Session, Depends(get_db)]) -> Response:
    """The business logo for the storefront and invoice pages (cacheable, nosniff)."""
    tenant = storefront.resolve_slug(db, tenant_slug)
    content, content_type = branding.logo_content(db, tenant.tenant_id)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


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
    session: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
) -> CustomerContextResponse:
    """Fixed path; the secrets travel only in private headers. Answers with the least the
    storefront needs (assurance, policy, business, display name, masked phone) or a constant 404."""
    response.headers["Cache-Control"] = PRIVATE_CACHE
    context = customer_access.require_context(db, capability, session)
    return CustomerContextResponse(
        assurance=context.assurance.value,
        tenant_slug=context.tenant_slug,
        display_name=context.display_name,
        required_policy=context.required_policy.value,
        granted=context.granted,
        contact_hint=context.contact_hint if not context.granted else "",
        has_saved_address=context.has_saved_address if context.granted else False,
    )


@storefront_public_router.post(
    "/customer-verification/start",
    status_code=status.HTTP_202_ACCEPTED,
    description="Supply X-Customer-Capability. Sends a one-time code to the customer's own phone.",
)
def start_customer_verification(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
    language: Annotated[str, Header(alias="Accept-Language")] = "en",
) -> dict[str, str]:
    response.headers["Cache-Control"] = PRIVATE_CACHE
    customer_verification.start_challenge(
        db, capability, "ar" if language.startswith("ar") else "en"
    )
    return {"status": "sent"}


@storefront_public_router.post(
    "/customer-verification/confirm",
    response_model=VerificationSessionResponse,
    description="Supply X-Customer-Capability and the code; returns the verified session secret.",
)
def confirm_customer_verification(
    request: VerificationConfirmRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
) -> VerificationSessionResponse:
    response.headers["Cache-Control"] = PRIVATE_CACHE
    secret, expires_at = customer_verification.confirm_challenge(db, capability, request.code)
    return VerificationSessionResponse(session=secret, expires_at=expires_at)


@storefront_public_router.delete(
    "/customer-verification/session", status_code=status.HTTP_204_NO_CONTENT
)
def end_customer_verification(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
    session: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
) -> None:
    response.headers["Cache-Control"] = PRIVATE_CACHE
    customer_verification.end_session(db, capability, session)


@storefront_public_router.get("/customer-verification/dev-code", include_in_schema=False)
def dev_verification_code(
    db: Annotated[Session, Depends(get_db)],
    capability: Annotated[str | None, Header(alias=CAPABILITY_HEADER)] = None,
) -> dict[str, str | None]:
    """Test-only: the last code the development adapter produced for this link's customer.
    Refused unless the provider is `dev` and the environment is not production."""
    settings = get_settings()
    if settings.customer_otp_provider != "dev" or settings.app_env.lower() == "production":
        raise AppError(404, "NOT_FOUND", "Not found")
    context = customer_access.resolve_state(db, capability)
    if context is None:
        raise AppError(404, "CUSTOMER_LINK_UNAVAILABLE", "This link is not available")
    return {"code": dev_delivery().latest_code(context.phone)}


def _status(db: Session, context: TenantContext, customer_id: UUID) -> CustomerLinkStatusResponse:
    from tawzeevo_api.services.cash_van import get_customer

    customer = get_customer(db, context.tenant.id, customer_id)
    active = customer_access.link_status(db, context.tenant.id, customer_id)
    return CustomerLinkStatusResponse(
        active=CustomerLinkResponse.model_validate(active) if active else None,
        effective_policy=customer_access.effective_policy(context.tenant, customer).value,
        policy_override=customer.access_policy_override,
        tenant_policy=context.tenant.customer_access_policy,
        available_policies=sorted(policy.value for policy in customer_access.selectable_policies()),
        verified_sessions=customer_verification.count_active_sessions(
            db, context.tenant.id, customer_id
        ),
    )


@storefront_owner_router.post(
    "/customers/{customer_id}/verified-sessions/revoke",
    response_model=CustomerLinkStatusResponse,
)
def revoke_verified_sessions(
    customer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CustomerLinkStatusResponse:
    """Owner ends every verified session of the customer; the link itself stays usable."""
    revoked = customer_verification.revoke_customer_sessions(
        db, context.tenant.id, customer_id, "owner_revoked"
    )
    db.add(
        AuditEvent(
            tenant_id=context.tenant.id,
            actor_user_id=context.membership.user_id,
            action="customer_verified_sessions_revoked",
            entity_type="customer",
            entity_id=customer_id,
            details={"count": revoked},
        )
    )
    commit_and_restore_tenant_scope(db, context.tenant.id)
    return _status(db, context, customer_id)


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


# ---------------------------------------------------------------------------------------------
# Guest checkout and provisional order page (P5-M4; D-046, D-049)
# ---------------------------------------------------------------------------------------------


@storefront_public_router.post(
    "/{tenant_slug}/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED
)
def guest_checkout(
    tenant_slug: str,
    request: CheckoutRequest,
    http_request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> CheckoutResponse:
    """One order per Idempotency-Key: a replay returns the original; a different body is 409.
    A granted personalized capability makes the order that customer's (D-090)."""
    response.headers["Cache-Control"] = PRIVATE_CACHE
    context = customer_access.resolve_context(
        db, http_request.headers.get(CAPABILITY_HEADER), http_request.headers.get(SESSION_HEADER)
    )
    return checkout.checkout(
        db,
        tenant_slug,
        request,
        idempotency_key,
        context,
        fuzzy_threshold=get_settings().invoice_fuzzy_match_threshold,
    )


@storefront_public_router.get("/order", response_model=ProvisionalOrderResponse)
def read_provisional_order(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    reference: Annotated[str | None, Header(alias="X-Order-Reference")] = None,
) -> ProvisionalOrderResponse:
    """Fixed path; the provisional reference travels only in the private header (D-046)."""
    response.headers["Cache-Control"] = PRIVATE_CACHE
    return checkout.provisional_order(db, reference)


@storefront_public_router.post(
    "/order/cancellation-request",
    response_model=CancellationRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_order_cancellation(
    body: CancellationRequestBody,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    reference: Annotated[str | None, Header(alias="X-Order-Reference")] = None,
) -> CancellationRequestResponse:
    """Customer asks; the owner decides (PHASE_05.md J). One pending request per order."""
    response.headers["Cache-Control"] = PRIVATE_CACHE
    ref = checkout.resolve_reference(db, reference)
    return CancellationRequestResponse.model_validate(
        orders.request_cancellation(db, ref, body.reason)
    )


# ---------------------------------------------------------------------------------------------
# Owner order review (P5-M5)
# ---------------------------------------------------------------------------------------------


def _detail(db: Session, tenant_id: UUID, order_id: UUID) -> OrderDetailResponse:
    order = orders.get_order(db, tenant_id, order_id)
    candidates = orders.candidate_customers(db, tenant_id, order)
    hint = None
    if order.intended_customer_id and all(c.id != order.intended_customer_id for c in candidates):
        hint = db.get(Customer, order.intended_customer_id)
    rows = ([hint] if hint else []) + candidates
    linked = db.get(Customer, order.linked_customer_id) if order.linked_customer_id else None
    deliveries = (
        db.scalars(
            select(DeliveryTask)
            .where(DeliveryTask.tenant_id == tenant_id, DeliveryTask.invoice_id == order.invoice_id)
            .order_by(DeliveryTask.created_at)
        ).all()
        if order.invoice_id
        else []
    )
    return OrderDetailResponse(
        order=OrderSummary.model_validate(order),
        invoice=orders.order_invoice_view(db, tenant_id, order),
        candidates=[
            CustomerCandidate(
                id=c.id,
                name=c.name,
                phone=c.phone,
                grade=c.grade.value if c.grade else None,
                is_hint=c.id == order.intended_customer_id,
            )
            for c in rows
        ],
        cancellation_requests=[
            CancellationRequestResponse.model_validate(r)
            for r in orders.list_cancellation_requests(db, tenant_id, order.id)
        ],
        linked_customer_name=linked.name if linked and linked.tenant_id == tenant_id else None,
        deliveries=[OrderDeliveryRef.model_validate(task) for task in deliveries],
    )


@storefront_owner_router.get("/orders", response_model=OrderListResponse)
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    status_filter: Annotated[str | None, Query(alias="status", max_length=12)] = None,
) -> OrderListResponse:
    rows = orders.list_orders(db, context.tenant.id, status_filter)
    return OrderListResponse(orders=[OrderSummary.model_validate(row) for row in rows])


@storefront_owner_router.get("/orders/{order_id}", response_model=OrderDetailResponse)
def read_order(
    order_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> OrderDetailResponse:
    return _detail(db, context.tenant.id, order_id)


@storefront_owner_router.post(
    "/orders/{order_id}/link-customer", response_model=OrderDetailResponse
)
def link_order_customer(
    order_id: UUID,
    request: LinkCustomerRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> OrderDetailResponse:
    """Explicit owner act (D-072): link an existing customer or create one from the snapshot."""
    create = None
    if request.create_from_snapshot:
        order = orders.get_order(db, context.tenant.id, order_id)
        create = CustomerCreateRequest(
            name=order.contact_name,
            phone=order.contact_phone_raw,
            address=order.contact_address,
            grade=request.grade,
        )
    orders.link_customer(
        db,
        context.tenant.id,
        context.membership.user_id,
        order_id,
        customer_id=request.customer_id,
        create=create,
        fuzzy_threshold=get_settings().invoice_fuzzy_match_threshold,
    )
    return _detail(db, context.tenant.id, order_id)


@storefront_owner_router.post("/orders/{order_id}/confirm", response_model=OrderDetailResponse)
def confirm_order(
    order_id: UUID,
    request: ConfirmOrderRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> OrderDetailResponse:
    orders.confirm_order(
        db, context.tenant.id, context.membership.user_id, order_id, request.expected_revision_id
    )
    return _detail(db, context.tenant.id, order_id)


@storefront_owner_router.post("/orders/{order_id}/decline", response_model=OrderDetailResponse)
def decline_order(
    order_id: UUID,
    request: DeclineOrderRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> OrderDetailResponse:
    orders.decline_order(db, context.tenant.id, context.membership.user_id, order_id, request.note)
    return _detail(db, context.tenant.id, order_id)


@storefront_owner_router.put("/orders/{order_id}/delivery-date", response_model=OrderDetailResponse)
def set_order_delivery_date(
    order_id: UUID,
    request: DeliveryDateRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> OrderDetailResponse:
    orders.set_delivery_date(
        db, context.tenant.id, context.membership.user_id, order_id, request.delivery_date
    )
    return _detail(db, context.tenant.id, order_id)


@storefront_owner_router.post(
    "/orders/cancellation-requests/{request_id}/decide",
    response_model=CancellationRequestResponse,
)
def decide_order_cancellation(
    request_id: UUID,
    request: CancellationDecisionRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> CancellationRequestResponse:
    row = orders.decide_cancellation(
        db,
        context.tenant.id,
        context.membership.user_id,
        request_id,
        approve=request.approve,
        note=request.note,
    )
    return CancellationRequestResponse.model_validate(row)


@storefront_owner_router.get("/notifications", response_model=NotificationListResponse)
def list_owner_notifications(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    unread_only: bool = False,
) -> NotificationListResponse:
    rows = orders.list_notifications(db, context.tenant.id, unread_only)
    unread = len(orders.list_notifications(db, context.tenant.id, True))
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(row) for row in rows], unread=unread
    )


@storefront_owner_router.post(
    "/notifications/{notification_id}/read", response_model=NotificationResponse
)
def read_owner_notification(
    notification_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> NotificationResponse:
    return NotificationResponse.model_validate(
        orders.mark_notification_read(db, context.tenant.id, notification_id)
    )
