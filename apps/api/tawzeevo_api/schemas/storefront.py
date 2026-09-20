from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from tawzeevo_api.schemas.branding import PublicBranding


class SlugResolution(BaseModel):
    tenant_id: UUID
    slug: str
    redirected_from: str | None


class StorefrontSettings(BaseModel):
    slug: str
    previous_slugs: list[str]
    published_products: int
    accepting_orders: bool
    customer_access_policy: str = "LINK"
    available_policies: list[str] = ["LINK"]


class StorefrontSlugRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=3, max_length=50)


class PublicCategory(BaseModel):
    id: UUID
    name_en: str
    name_ar: str
    slug: str
    product_count: int


class PublicImage(BaseModel):
    id: UUID
    url: str
    width: int
    height: int
    alt_text: str | None


class PublicPackaging(BaseModel):
    pieces_per_box: int | None
    piece_price: str
    box_price: str | None


class PublicProduct(BaseModel):
    """Public commercial facts only: no stock, availability, grade, cost or supplier data."""

    id: UUID
    category_id: UUID
    name: str
    name_ar: str | None
    barcode: str | None
    currency: str
    price: str
    pricing: str = "public"  # "public" | "personalized" (never the grade or the rule)
    price_basis: str
    packaging: PublicPackaging
    images: list[PublicImage]


class PublicProductPage(BaseModel):
    items: list[PublicProduct]
    page: int
    page_size: int
    total: int
    has_more: bool


class PublicStorefront(BaseModel):
    slug: str
    redirected_from: str | None
    name: str
    accepting_orders: bool
    categories: list[PublicCategory]
    published_products: int
    generated_at: datetime
    branding: PublicBranding | None = None


class ViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=8, max_length=128)


class ViewResponse(BaseModel):
    counted: bool


class FeaturedResponse(BaseModel):
    items: list[PublicProduct]


class CampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    priority: int = Field(default=0, ge=0, le=1000)


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_product_id: UUID
    starts_at: datetime
    ends_at: datetime
    priority: int
    created_at: datetime
    cancelled_at: datetime | None
    active: bool = False


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]


class CustomerLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    rotated_from_id: UUID | None


class IssuedCustomerLinkResponse(CustomerLinkResponse):
    """The raw secret is returned exactly once, as a storefront path with a fragment."""

    storefront_path: str


class CustomerLinkStatusResponse(BaseModel):
    active: CustomerLinkResponse | None
    effective_policy: str
    policy_override: str | None
    tenant_policy: str
    available_policies: list[str]
    verified_sessions: int = 0


class CustomerPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    override: str | None = Field(default=None, max_length=20)


class TenantPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str = Field(max_length=20)


class CustomerContextResponse(BaseModel):
    """Everything the storefront may know about a personalized visitor: no grade, no history.
    `granted` is false while the policy asks for more assurance than the visitor holds (then the
    storefront offers verification and shows only the masked phone hint)."""

    assurance: str
    tenant_slug: str
    display_name: str
    required_policy: str = "LINK"
    granted: bool = True
    contact_hint: str = ""


class VerificationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=4, max_length=12)


class VerificationSessionResponse(BaseModel):
    session: str
    expires_at: datetime
