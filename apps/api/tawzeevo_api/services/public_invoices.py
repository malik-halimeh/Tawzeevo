"""Capability authorization and explicit public projection, independent of user login."""

import hashlib
import re
import secrets
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Invoice,
    InvoiceRevisionItem,
    PublicInvoiceCapability,
    Tenant,
    TenantStatus,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.public_invoices import (
    CapabilityResponse,
    IssuedCapabilityResponse,
    PublicInvoiceItem,
    PublicInvoiceResponse,
)
from tawzeevo_api.services.invoice_finance import _locked_invoice, _revision

TOKEN_PATTERN = re.compile(r"[a-f0-9]{32}\.[A-Za-z0-9_-]{43}")
PUBLIC_PATH = "/api/v1/public/invoice"


def _unavailable() -> AppError:
    return AppError(404, "PUBLIC_INVOICE_UNAVAILABLE", "Invoice link is invalid or unavailable")


def _audit(db: Session, cap: PublicInvoiceCapability, actor: UUID, action: str) -> None:
    db.add(
        AuditEvent(
            tenant_id=cap.tenant_id,
            actor_user_id=actor,
            action=action,
            entity_type="public_invoice_capability",
            entity_id=cap.id,
            details={"invoice_id": str(cap.invoice_id)},
        )
    )


def list_capabilities(db: Session, tenant_id: UUID, invoice_id: UUID) -> list[CapabilityResponse]:
    _locked_invoice(db, tenant_id, invoice_id)
    return [
        CapabilityResponse.model_validate(cap)
        for cap in db.scalars(
            select(PublicInvoiceCapability)
            .where(
                PublicInvoiceCapability.tenant_id == tenant_id,
                PublicInvoiceCapability.invoice_id == invoice_id,
            )
            .order_by(PublicInvoiceCapability.created_at.desc(), PublicInvoiceCapability.id.desc())
        )
    ]


def issue_capability(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    invoice_id: UUID,
    *,
    rotate_id: UUID | None = None,
) -> IssuedCapabilityResponse:
    invoice = _locked_invoice(db, tenant_id, invoice_id)
    revision = _revision(db, tenant_id, invoice)
    now = datetime.now(UTC)
    if rotate_id is not None:
        old = _owned_capability(db, tenant_id, invoice_id, rotate_id)
        if old.revoked_at is not None:
            raise AppError(409, "CAPABILITY_REVOKED", "This link has already been revoked")
        old.revoked_at = now
        _audit(db, old, actor, "invoice_capability_rotated")
    # Tenant is only a lookup hint. The 256-bit random secret authorizes exactly one invoice.
    raw = f"{tenant_id.hex}.{secrets.token_urlsafe(32)}"
    cap = PublicInvoiceCapability(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        token_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=now + timedelta(days=90),
        rotated_from_id=rotate_id,
        created_by_user_id=actor,
    )
    db.add(cap)
    db.flush()
    _audit(db, cap, actor, "invoice_capability_created")
    phone: str | None = None
    snapshot_phone = revision.customer_snapshot.get("phone")
    if isinstance(snapshot_phone, str):
        with suppress(InvalidPhoneNumberError):
            phone = normalize_phone(snapshot_phone)
    tenant = db.get(Tenant, tenant_id)
    summary = (
        f"{tenant.name if tenant else 'Tawzeevo'} — Invoice / فاتورة "
        f"{invoice.official_invoice_number or 'Draft / مسودة'}\n"
        f"{invoice.status} · {revision.net_sales:.4f} {revision.currency}"
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(cap)
    return IssuedCapabilityResponse(
        **CapabilityResponse.model_validate(cap).model_dump(),
        public_path=f"{PUBLIC_PATH}#{raw}",
        customer_phone=phone,
        summary=summary,
    )


def _owned_capability(
    db: Session,
    tenant_id: UUID,
    invoice_id: UUID,
    capability_id: UUID,
) -> PublicInvoiceCapability:
    cap = db.scalar(
        select(PublicInvoiceCapability)
        .where(
            PublicInvoiceCapability.tenant_id == tenant_id,
            PublicInvoiceCapability.invoice_id == invoice_id,
            PublicInvoiceCapability.id == capability_id,
        )
        .with_for_update()
    )
    if cap is None:
        raise AppError(404, "CAPABILITY_NOT_FOUND", "Invoice link was not found")
    return cap


def revoke_capability(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    invoice_id: UUID,
    capability_id: UUID,
) -> None:
    _locked_invoice(db, tenant_id, invoice_id)
    cap = _owned_capability(db, tenant_id, invoice_id, capability_id)
    if cap.revoked_at is None:
        cap.revoked_at = datetime.now(UTC)
        _audit(db, cap, actor, "invoice_capability_revoked")
        commit_and_restore_tenant_scope(db, tenant_id)


def resolve_public_invoice(db: Session, raw: str) -> PublicInvoiceResponse:
    if not TOKEN_PATTERN.fullmatch(raw):
        raise _unavailable()
    tenant_id = UUID(hex=raw[:32])
    set_tenant_scope(db, tenant_id)
    cap = db.scalar(
        select(PublicInvoiceCapability).where(
            PublicInvoiceCapability.tenant_id == tenant_id,
            PublicInvoiceCapability.token_sha256 == hashlib.sha256(raw.encode()).hexdigest(),
            PublicInvoiceCapability.revoked_at.is_(None),
            PublicInvoiceCapability.expires_at > datetime.now(UTC),
        )
    )
    if cap is None:
        raise _unavailable()
    # No tenant business reads occur before the secret has been validated.
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE:
        raise _unavailable()
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.id == cap.invoice_id,
        )
    )
    if invoice is None:
        raise _unavailable()
    revision = _revision(db, tenant_id, invoice)
    items = list(
        db.scalars(
            select(InvoiceRevisionItem)
            .where(
                InvoiceRevisionItem.tenant_id == tenant_id,
                InvoiceRevisionItem.invoice_revision_id == revision.id,
            )
            .order_by(InvoiceRevisionItem.line_number)
        )
    )
    name = revision.customer_snapshot.get("name")
    # Never serialize an owner response, arbitrary snapshot dict, or ORM row here.
    return PublicInvoiceResponse(
        business_name=tenant.name,
        customer_name=name if isinstance(name, str) else None,
        status=invoice.status,
        number=invoice.official_invoice_number,
        revision=revision.server_revision_number,
        currency=revision.currency,
        subtotal=revision.subtotal,
        discount=revision.discount_total,
        markup=revision.markup_total,
        net_sales=revision.net_sales,
        items=[
            PublicInvoiceItem(
                name=item.product_name,
                barcode=item.barcode,
                quantity=item.quantity,
                unit=item.price_basis,
                pieces_per_box=item.pieces_per_box,
                unit_price=item.effective_unit_price,
                discount=item.line_discount,
                markup=item.line_markup,
                total=item.line_total,
            )
            for item in items
        ],
    )
