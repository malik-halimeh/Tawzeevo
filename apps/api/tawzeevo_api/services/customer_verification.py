"""Customer verification (PHASE_09.md P9-M5, D-072/D-073): a personalized link holder proves
they control the customer's own phone number by entering a one-time code, and receives a
verified session bound to that link.

Properties: the code is stored as a hash and never logged; short expiry; bounded wrong attempts
consume the challenge; starts are throttled per customer; a provider outage is a clean 503 with
no session issued and no lock-in; the session is hash-only, expiring, revocable, and dies with
the link; the customer's phone change never breaks identity (everything keys on customer_id);
a session started from one link can never satisfy another customer's link."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api import metrics
from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    CustomerVerificationChallenge,
    CustomerVerifiedSession,
    Tenant,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.services.customer_access import CustomerContext, resolve_state
from tawzeevo_api.services.otp_delivery import DeliveryUnavailable, OtpMessage, get_otp_delivery

_CODE_DIGITS = 6


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _unavailable() -> AppError:
    return AppError(404, "CUSTOMER_LINK_UNAVAILABLE", "This link is not available")


def _context_for(db: Session, capability: str | None) -> CustomerContext:
    context = resolve_state(db, capability)
    if context is None:
        raise _unavailable()
    return context


def start_challenge(
    db: Session, capability: str | None, language: str, settings: Settings | None = None
) -> None:
    """Send a fresh code to the customer's own phone. Always answers the same way once the link
    is valid; the storefront shows only a masked phone hint."""
    active = settings or get_settings()
    context = _context_for(db, capability)
    now = datetime.now(UTC)
    recent = db.scalar(
        select(func.count())
        .select_from(CustomerVerificationChallenge)
        .where(
            CustomerVerificationChallenge.tenant_id == context.tenant_id,
            CustomerVerificationChallenge.customer_id == context.customer_id,
            CustomerVerificationChallenge.created_at > now - timedelta(hours=1),
        )
    )
    if (recent or 0) >= active.customer_otp_starts_per_hour:
        metrics.increment("otp_throttled")
        raise AppError(429, "VERIFICATION_RATE_LIMITED", "Too many codes requested; try later")
    # A new code supersedes any open one for this customer.
    for open_challenge in db.scalars(
        select(CustomerVerificationChallenge).where(
            CustomerVerificationChallenge.tenant_id == context.tenant_id,
            CustomerVerificationChallenge.customer_id == context.customer_id,
            CustomerVerificationChallenge.consumed_at.is_(None),
        )
    ):
        open_challenge.consumed_at = now
        open_challenge.consumed_reason = "superseded"
    code = f"{secrets.randbelow(10**_CODE_DIGITS):0{_CODE_DIGITS}d}"
    delivery = get_otp_delivery(active)
    challenge = CustomerVerificationChallenge(
        tenant_id=context.tenant_id,
        customer_id=context.customer_id,
        link_id=context.link_id,
        code_sha256=_hash(code),
        channel=delivery.channel,
        expires_at=now + timedelta(minutes=active.customer_otp_ttl_minutes),
    )
    db.add(challenge)
    db.add(
        AuditEvent(
            tenant_id=context.tenant_id,
            action="customer_verification_started",
            entity_type="customer",
            entity_id=context.customer_id,
            details={"channel": delivery.channel},
        )
    )
    tenant = db.get(Tenant, context.tenant_id)
    business_name = tenant.name if tenant else "Tawzeevo"
    try:
        delivery.send(OtpMessage(context.phone, code, language, business_name))
    except DeliveryUnavailable as exc:
        # Nothing usable is left behind: the challenge is closed before anyone could guess it.
        challenge.consumed_at = now
        challenge.consumed_reason = "delivery_failed"
        commit_and_restore_tenant_scope(db, context.tenant_id)
        metrics.increment("otp_delivery_failures")
        raise AppError(503, "VERIFICATION_UNAVAILABLE", "Verification is unavailable now") from exc
    commit_and_restore_tenant_scope(db, context.tenant_id)
    metrics.increment("otp_sent")


def confirm_challenge(
    db: Session, capability: str | None, code: str, settings: Settings | None = None
) -> tuple[str, datetime]:
    """Trade the correct code for a verified session secret. Wrong codes count against the open
    challenge; too many consume it; expired and consumed challenges are refused the same way."""
    active = settings or get_settings()
    context = _context_for(db, capability)
    now = datetime.now(UTC)
    challenge = db.scalar(
        select(CustomerVerificationChallenge)
        .where(
            CustomerVerificationChallenge.tenant_id == context.tenant_id,
            CustomerVerificationChallenge.customer_id == context.customer_id,
            CustomerVerificationChallenge.link_id == context.link_id,
            CustomerVerificationChallenge.consumed_at.is_(None),
        )
        .order_by(CustomerVerificationChallenge.created_at.desc())
        .with_for_update()
    )
    invalid = AppError(400, "VERIFICATION_CODE_INVALID", "The code is wrong or no longer valid")
    if challenge is None:
        raise invalid
    if challenge.expires_at <= now:
        challenge.consumed_at = now
        challenge.consumed_reason = "expired"
        commit_and_restore_tenant_scope(db, context.tenant_id)
        raise invalid
    if not secrets.compare_digest(challenge.code_sha256, _hash(code.strip())):
        challenge.attempts += 1
        if challenge.attempts >= active.customer_otp_max_attempts:
            challenge.consumed_at = now
            challenge.consumed_reason = "too_many_attempts"
            metrics.increment("otp_locked")
        commit_and_restore_tenant_scope(db, context.tenant_id)
        metrics.increment("otp_wrong")
        raise invalid
    challenge.consumed_at = now
    challenge.consumed_reason = "verified"
    secret = f"{context.tenant_id.hex}.{secrets.token_urlsafe(32)}"
    session = CustomerVerifiedSession(
        tenant_id=context.tenant_id,
        customer_id=context.customer_id,
        link_id=context.link_id,
        token_sha256=_hash(secret),
        expires_at=now + timedelta(days=active.customer_verified_session_days),
    )
    db.add(session)
    db.add(
        AuditEvent(
            tenant_id=context.tenant_id,
            action="customer_verified",
            entity_type="customer",
            entity_id=context.customer_id,
            details={"session_days": active.customer_verified_session_days},
        )
    )
    commit_and_restore_tenant_scope(db, context.tenant_id)
    metrics.increment("otp_verified")
    return secret, session.expires_at


def end_session(db: Session, capability: str | None, session_raw: str | None) -> None:
    """Customer-initiated sign-out of the verified session; the link itself stays valid."""
    context = resolve_state(db, capability)
    if context is None or not session_raw:
        return
    row = db.scalar(
        select(CustomerVerifiedSession).where(
            CustomerVerifiedSession.tenant_id == context.tenant_id,
            CustomerVerifiedSession.token_sha256 == _hash(session_raw),
            CustomerVerifiedSession.revoked_at.is_(None),
        )
    )
    if row is not None:
        row.revoked_at = datetime.now(UTC)
        row.revoked_reason = "signed_out"
        commit_and_restore_tenant_scope(db, context.tenant_id)


def revoke_customer_sessions(db: Session, tenant_id: UUID, customer_id: UUID, reason: str) -> int:
    """Owner action: end every verified session of a customer (the link stays)."""
    rows = list(
        db.scalars(
            select(CustomerVerifiedSession).where(
                CustomerVerifiedSession.tenant_id == tenant_id,
                CustomerVerifiedSession.customer_id == customer_id,
                CustomerVerifiedSession.revoked_at.is_(None),
            )
        )
    )
    now = datetime.now(UTC)
    for row in rows:
        row.revoked_at = now
        row.revoked_reason = reason
    return len(rows)


def count_active_sessions(db: Session, tenant_id: UUID, customer_id: UUID) -> int:
    now = datetime.now(UTC)
    return int(
        db.scalar(
            select(func.count())
            .select_from(CustomerVerifiedSession)
            .where(
                CustomerVerifiedSession.tenant_id == tenant_id,
                CustomerVerifiedSession.customer_id == customer_id,
                CustomerVerifiedSession.revoked_at.is_(None),
                CustomerVerifiedSession.expires_at > now,
            )
        )
        or 0
    )
