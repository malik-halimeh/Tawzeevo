"""Tenant branding shapes (PHASE_08.md F). Presentation only."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_COLOR = r"^#[0-9a-fA-F]{6}$"
_SOCIAL_KEYS = {"instagram", "facebook", "tiktok", "website", "x", "youtube"}


class BrandingUpdateRequest(BaseModel):
    """Partial update; every field optional; blank strings clear a value."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int | None = Field(default=None, ge=1)
    description: str | None = Field(default=None, max_length=1000)
    phone: str | None = Field(default=None, max_length=32)
    whatsapp: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    primary_color: str | None = Field(default=None, pattern=_COLOR)
    secondary_color: str | None = Field(default=None, pattern=_COLOR)
    storefront_title: str | None = Field(default=None, max_length=120)
    banner_text: str | None = Field(default=None, max_length=300)
    social_links: dict[str, str] | None = None
    about_text: str | None = Field(default=None, max_length=4000)
    contact_text: str | None = Field(default=None, max_length=2000)
    privacy_text: str | None = Field(default=None, max_length=8000)
    terms_text: str | None = Field(default=None, max_length=8000)
    invoice_header: str | None = Field(default=None, max_length=500)
    invoice_footer: str | None = Field(default=None, max_length=500)
    invoice_terms: str | None = Field(default=None, max_length=2000)
    thank_you_text: str | None = Field(default=None, max_length=300)
    invoice_qr_enabled: bool | None = None
    default_language: str | None = Field(default=None, pattern=r"^(en|ar)$")
    date_format: str | None = Field(default=None, pattern=r"^(DD/MM/YYYY|YYYY-MM-DD|MM/DD/YYYY)$")
    timezone: str | None = Field(default=None, max_length=64)
    display_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @field_validator("social_links")
    @classmethod
    def validate_social(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        cleaned: dict[str, str] = {}
        for key, url in value.items():
            if key not in _SOCIAL_KEYS:
                raise ValueError(f"unknown social link {key}")
            url = url.strip()
            if not url:
                continue
            if not url.startswith("https://"):
                raise ValueError("social links must start with https://")
            cleaned[key] = url[:300]
        return cleaned


class BrandingResponse(BaseModel):
    """Owner view of the branding row (defaults when none was saved yet)."""

    tenant_id: UUID
    business_name: str
    description: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    address: str | None
    primary_color: str | None
    secondary_color: str | None
    storefront_title: str | None
    banner_text: str | None
    social_links: dict[str, str]
    about_text: str | None
    contact_text: str | None
    privacy_text: str | None
    terms_text: str | None
    invoice_header: str | None
    invoice_footer: str | None
    invoice_terms: str | None
    thank_you_text: str | None
    invoice_qr_enabled: bool
    default_language: str
    date_format: str
    timezone: str
    display_currency: str | None
    has_logo: bool
    logo_path: str | None
    version: int
    updated_at: datetime | None


class PublicBranding(BaseModel):
    """What the storefront may show anyone: identity, contact, theme, texts, logo path."""

    business_name: str
    description: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    address: str | None
    primary_color: str | None
    secondary_color: str | None
    storefront_title: str | None
    banner_text: str | None
    social_links: dict[str, str]
    about_text: str | None
    contact_text: str | None
    privacy_text: str | None
    terms_text: str | None
    default_language: str
    logo_path: str | None


class InvoiceBranding(BaseModel):
    """Customer invoice page block. Business contact fields are named so the projection guard
    (`phone` never appears on the public invoice) keeps protecting the customer's data."""

    business_name: str
    logo_path: str | None
    business_tel: str | None
    business_whatsapp: str | None
    business_location: str | None
    invoice_header: str | None
    invoice_footer: str | None
    invoice_terms: str | None
    thank_you_text: str | None
    invoice_qr_enabled: bool
    default_language: str
    date_format: str
