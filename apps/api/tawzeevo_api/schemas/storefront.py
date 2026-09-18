from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SlugResolution(BaseModel):
    tenant_id: UUID
    slug: str
    redirected_from: str | None


class StorefrontSettings(BaseModel):
    slug: str
    previous_slugs: list[str]
    published_products: int
    accepting_orders: bool


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
