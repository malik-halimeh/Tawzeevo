"""Tenant branding (PHASE_08.md F). Presentation settings read by the owner desk, the public
storefront and the customer invoice page. Nothing here reaches pricing, ledgers, roles or scope.
The logo goes through the same validated image processing and object storage as product images."""

from __future__ import annotations

import contextlib
from uuid import UUID

from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import AuditEvent, Tenant, TenantBranding
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.branding import (
    BrandingResponse,
    BrandingUpdateRequest,
    InvoiceBranding,
    PublicBranding,
)
from tawzeevo_api.services.media import get_object_storage, process_product_image

_TEXT_FIELDS = (
    "description",
    "address",
    "storefront_title",
    "banner_text",
    "about_text",
    "contact_text",
    "privacy_text",
    "terms_text",
    "invoice_header",
    "invoice_footer",
    "invoice_terms",
    "thank_you_text",
)


def _row(db: Session, tenant_id: UUID, create: bool = False) -> TenantBranding | None:
    set_tenant_scope(db, tenant_id)
    row = db.get(TenantBranding, tenant_id)
    if row is None and create:
        row = TenantBranding(tenant_id=tenant_id)
        db.add(row)
        db.flush()
    return row


def logo_path(tenant_id: UUID, row: TenantBranding | None, slug: str | None) -> str | None:
    if row is None or row.logo_object_key is None or slug is None:
        return None
    return f"/api/v1/public/{slug}/branding/logo?v={row.version}"


def branding_response(db: Session, tenant_id: UUID) -> BrandingResponse:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant was not found")
    row = _row(db, tenant_id)
    if row is None:
        return BrandingResponse(
            tenant_id=tenant_id,
            business_name=tenant.name,
            description=None,
            phone=None,
            whatsapp=None,
            email=None,
            address=None,
            primary_color=None,
            secondary_color=None,
            storefront_title=None,
            banner_text=None,
            social_links={},
            about_text=None,
            contact_text=None,
            privacy_text=None,
            terms_text=None,
            invoice_header=None,
            invoice_footer=None,
            invoice_terms=None,
            thank_you_text=None,
            invoice_qr_enabled=False,
            default_language="en",
            date_format="DD/MM/YYYY",
            timezone="Asia/Beirut",
            display_currency=None,
            has_logo=False,
            logo_path=None,
            version=0,
            updated_at=None,
        )
    return BrandingResponse(
        tenant_id=tenant_id,
        business_name=tenant.name,
        description=row.description,
        phone=row.phone,
        whatsapp=row.whatsapp,
        email=row.email,
        address=row.address,
        primary_color=row.primary_color,
        secondary_color=row.secondary_color,
        storefront_title=row.storefront_title,
        banner_text=row.banner_text,
        social_links=dict(row.social_links or {}),
        about_text=row.about_text,
        contact_text=row.contact_text,
        privacy_text=row.privacy_text,
        terms_text=row.terms_text,
        invoice_header=row.invoice_header,
        invoice_footer=row.invoice_footer,
        invoice_terms=row.invoice_terms,
        thank_you_text=row.thank_you_text,
        invoice_qr_enabled=row.invoice_qr_enabled,
        default_language=row.default_language,
        date_format=row.date_format,
        timezone=row.timezone,
        display_currency=row.display_currency,
        has_logo=row.logo_object_key is not None,
        logo_path=logo_path(tenant_id, row, tenant.slug),
        version=row.version,
        updated_at=row.updated_at,
    )


def update_branding(
    db: Session, tenant_id: UUID, actor: UUID, request: BrandingUpdateRequest
) -> BrandingResponse:
    existing = _row(db, tenant_id)
    created = existing is None
    row = existing or _row(db, tenant_id, create=True)
    assert row is not None
    if (
        not created
        and request.expected_version is not None
        and request.expected_version != row.version
    ):
        raise AppError(409, "BRANDING_VERSION_CONFLICT", "Branding was changed elsewhere; reload")
    values = request.model_dump(exclude={"expected_version"}, exclude_unset=True)
    changed: list[str] = []
    for key, value in values.items():
        if key in ("phone", "whatsapp") and value:
            try:
                value = normalize_phone(str(value))
            except InvalidPhoneNumberError as exc:
                raise AppError(422, "INVALID_PHONE", f"{key} is not a valid phone number") from exc
        if key in _TEXT_FIELDS and isinstance(value, str):
            value = value.strip() or None
        if key == "email" and value is not None:
            value = str(value)
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed.append(key)
    if changed:
        if not created:
            row.version += 1  # a brand-new row is version 1 already
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor,
                action="branding_updated",
                entity_type="tenant_branding",
                entity_id=tenant_id,
                details={"fields": ",".join(changed)},
            )
        )
    commit_and_restore_tenant_scope(db, tenant_id)
    return branding_response(db, tenant_id)


def upload_logo(
    db: Session, tenant_id: UUID, actor: UUID, content: bytes, content_type: str | None
) -> BrandingResponse:
    processed = process_product_image(content, content_type)
    row = _row(db, tenant_id, create=True)
    assert row is not None
    storage = get_object_storage()
    object_key = f"tenants/{tenant_id}/branding/logo-{processed.sha256[:16]}.webp"
    storage.put_bytes(object_key, processed.content)
    previous = row.logo_object_key
    row.logo_object_key = object_key
    row.logo_content_type = processed.content_type
    row.logo_width = processed.width
    row.logo_height = processed.height
    row.version += 1
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="branding_logo_uploaded",
            entity_type="tenant_branding",
            entity_id=tenant_id,
            details={"object_key": object_key},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    if previous and previous != object_key:
        with contextlib.suppress(Exception):  # a stale object is harmless
            storage.delete(previous)
    return branding_response(db, tenant_id)


def logo_content(db: Session, tenant_id: UUID) -> tuple[bytes, str]:
    row = _row(db, tenant_id)
    if row is None or row.logo_object_key is None:
        raise AppError(404, "LOGO_NOT_FOUND", "No logo")
    return get_object_storage().get_bytes(row.logo_object_key), row.logo_content_type or "image/png"


def public_branding(db: Session, tenant: Tenant) -> PublicBranding:
    row = _row(db, tenant.id)
    return PublicBranding(
        business_name=tenant.name,
        description=row.description if row else None,
        phone=row.phone if row else None,
        whatsapp=row.whatsapp if row else None,
        email=row.email if row else None,
        address=row.address if row else None,
        primary_color=row.primary_color if row else None,
        secondary_color=row.secondary_color if row else None,
        storefront_title=row.storefront_title if row else None,
        banner_text=row.banner_text if row else None,
        social_links=dict(row.social_links or {}) if row else {},
        about_text=row.about_text if row else None,
        contact_text=row.contact_text if row else None,
        privacy_text=row.privacy_text if row else None,
        terms_text=row.terms_text if row else None,
        default_language=row.default_language if row else "en",
        logo_path=logo_path(tenant.id, row, tenant.slug),
    )


def invoice_branding(db: Session, tenant: Tenant) -> InvoiceBranding:
    row = _row(db, tenant.id)
    return InvoiceBranding(
        business_name=tenant.name,
        logo_path=logo_path(tenant.id, row, tenant.slug),
        business_tel=row.phone if row else None,
        business_whatsapp=row.whatsapp if row else None,
        business_location=row.address if row else None,
        invoice_header=row.invoice_header if row else None,
        invoice_footer=row.invoice_footer if row else None,
        invoice_terms=row.invoice_terms if row else None,
        thank_you_text=row.thank_you_text if row else None,
        invoice_qr_enabled=row.invoice_qr_enabled if row else False,
        default_language=row.default_language if row else "en",
        date_format=row.date_format if row else "DD/MM/YYYY",
    )
