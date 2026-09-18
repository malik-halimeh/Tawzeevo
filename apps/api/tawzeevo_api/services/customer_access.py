"""Personalized customer storefront links and the customer access context.

PHASE_05.md C.1; D-071 (opaque link → exact customer, one active per customer, atomic rotation,
revocation, no automatic expiry, hash-only), D-072 (assurance levels; LINK grants pricing,
catalog and order submission for owner review only), D-075 (contexts are re-resolved on every
request, so rotation/revocation/suspension end them at once). Nothing here proves identity and
nothing here grants financial authority.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Customer,
    CustomerAccessLink,
    CustomerGrade,
    Tenant,
    TenantStatus,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope

# Same shape as the invoice capability (tenant hex + 43 url-safe chars) so the existing access-log
# redaction pattern covers it and the tenant scope can be set before the hashed lookup.
TOKEN_PATTERN = re.compile(r"[a-f0-9]{32}\.[A-Za-z0-9_-]{43}")
PUBLIC_ENTRY_PATH = "/access"  # storefront: /{slug}/access#<secret>


class Assurance(StrEnum):
    ANONYMOUS = "ANONYMOUS"
    LINK = "LINK"
    VERIFIED = "VERIFIED"
    ACCOUNT = "ACCOUNT"


class AccessPolicy(StrEnum):
    LINK = "LINK"
    VERIFIED = "VERIFIED"
    ACCOUNT_REQUIRED = "ACCOUNT_REQUIRED"


# Phase 5 can satisfy only LINK; the others exist for later assurance levels (D-072, D-073, D-074).
AVAILABLE_POLICIES = frozenset({AccessPolicy.LINK})


@dataclass(frozen=True)
class CustomerContext:
    """What a valid personalized link grants: identity of the intended customer, nothing more."""

    tenant_id: UUID
    tenant_slug: str
    customer_id: UUID
    display_name: str
    grade: CustomerGrade | None  # used for pricing only; never serialized to the public
    assurance: Assurance
    link_id: UUID


def _unavailable() -> AppError:
    # Constant failure: never reveals whether a customer, link or business exists.
    return AppError(404, "CUSTOMER_LINK_UNAVAILABLE", "This link is not available")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def effective_policy(tenant: Tenant, customer: Customer) -> AccessPolicy:
    override = customer.access_policy_override
    return AccessPolicy(override) if override else AccessPolicy(tenant.customer_access_policy)


def validate_policy(value: str) -> AccessPolicy:
    try:
        policy = AccessPolicy(value)
    except ValueError as exc:
        raise AppError(422, "ACCESS_POLICY_INVALID", "Unknown access policy") from exc
    if policy not in AVAILABLE_POLICIES:
        raise AppError(
            409,
            "ACCESS_POLICY_NOT_AVAILABLE",
            "This access policy is not available yet; only LINK can be enforced",
        )
    return policy


# ---------------------------------------------------------------------------------------------
# Owner lifecycle
# ---------------------------------------------------------------------------------------------


def _locked_customer(db: Session, tenant_id: UUID, customer_id: UUID) -> Customer:
    customer = db.scalar(
        select(Customer)
        .where(Customer.tenant_id == tenant_id, Customer.id == customer_id)
        .with_for_update()
    )
    if customer is None:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
    return customer


def _active_link(db: Session, tenant_id: UUID, customer_id: UUID) -> CustomerAccessLink | None:
    return db.scalar(
        select(CustomerAccessLink).where(
            CustomerAccessLink.tenant_id == tenant_id,
            CustomerAccessLink.customer_id == customer_id,
            CustomerAccessLink.revoked_at.is_(None),
        )
    )


def _audit(db: Session, link: CustomerAccessLink, actor: UUID, action: str) -> None:
    db.add(
        AuditEvent(
            tenant_id=link.tenant_id,
            actor_user_id=actor,
            action=action,
            entity_type="customer_access_link",
            entity_id=link.id,
            details={"customer_id": str(link.customer_id)},
        )
    )


def issue_link(
    db: Session, tenant_id: UUID, actor: UUID, customer_id: UUID
) -> tuple[CustomerAccessLink, str]:
    """Issue or rotate: under the customer row lock the earlier active link is revoked and the
    new one inserted in the same transaction, so there is never a moment with two or zero
    usable links during a rotation (D-071). Returns the raw secret exactly once."""
    _locked_customer(db, tenant_id, customer_id)
    now = datetime.now(UTC)
    previous = _active_link(db, tenant_id, customer_id)
    rotated_from: UUID | None = None
    if previous is not None:
        previous.revoked_at = now
        previous.revoked_reason = "rotated"
        rotated_from = previous.id
        db.flush()
        _audit(db, previous, actor, "customer_link_rotated")
    raw = f"{tenant_id.hex}.{secrets.token_urlsafe(32)}"
    link = CustomerAccessLink(
        tenant_id=tenant_id,
        customer_id=customer_id,
        token_sha256=_hash(raw),
        created_by_user_id=actor,
        rotated_from_id=rotated_from,
    )
    db.add(link)
    db.flush()
    _audit(db, link, actor, "customer_link_issued")
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(link)
    return link, raw


def revoke_link(db: Session, tenant_id: UUID, actor: UUID, customer_id: UUID) -> CustomerAccessLink:
    """Revocation without replacement: the customer falls back to the anonymous storefront."""
    _locked_customer(db, tenant_id, customer_id)
    link = _active_link(db, tenant_id, customer_id)
    if link is None:
        raise AppError(404, "CUSTOMER_LINK_NOT_FOUND", "This customer has no active link")
    link.revoked_at = datetime.now(UTC)
    link.revoked_reason = "revoked"
    _audit(db, link, actor, "customer_link_revoked")
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(link)
    return link


def link_status(db: Session, tenant_id: UUID, customer_id: UUID) -> CustomerAccessLink | None:
    set_tenant_scope(db, tenant_id)
    return _active_link(db, tenant_id, customer_id)


def set_customer_policy(
    db: Session, tenant_id: UUID, actor: UUID, customer_id: UUID, policy: str | None
) -> Customer:
    customer = _locked_customer(db, tenant_id, customer_id)
    customer.access_policy_override = validate_policy(policy).value if policy else None
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="customer_access_policy_changed",
            entity_type="customer",
            entity_id=customer.id,
            details={"override": customer.access_policy_override},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(customer)
    return customer


def set_tenant_policy(db: Session, tenant: Tenant, actor: UUID, policy: str) -> Tenant:
    tenant.customer_access_policy = validate_policy(policy).value
    db.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor_user_id=actor,
            action="tenant_access_policy_changed",
            entity_type="tenant",
            entity_id=tenant.id,
            details={"policy": tenant.customer_access_policy},
        )
    )
    commit_and_restore_tenant_scope(db, tenant.id)
    return tenant


# ---------------------------------------------------------------------------------------------
# Public resolution
# ---------------------------------------------------------------------------------------------


def resolve_context(db: Session, raw: str | None, *, touch: bool = False) -> CustomerContext | None:
    """Resolve a capability to its customer context, or None for anything that is not a live,
    policy-permitted link of an ACTIVE business. Never raises for a bad secret: an absent context
    simply means the anonymous storefront (D-072)."""
    if not raw or not TOKEN_PATTERN.fullmatch(raw):
        return None
    tenant_id = UUID(hex=raw[:32])
    set_tenant_scope(db, tenant_id)
    now = datetime.now(UTC)
    link = db.scalar(
        select(CustomerAccessLink).where(
            CustomerAccessLink.tenant_id == tenant_id,
            CustomerAccessLink.token_sha256 == _hash(raw),
            CustomerAccessLink.revoked_at.is_(None),
        )
    )
    if link is None or (link.expires_at is not None and link.expires_at <= now):
        return None
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status is not TenantStatus.ACTIVE:
        return None
    customer = db.scalar(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.id == link.customer_id)
    )
    if customer is None or effective_policy(tenant, customer) is not AccessPolicy.LINK:
        return None
    if touch:
        link.last_used_at = now
        commit_and_restore_tenant_scope(db, tenant_id)
    return CustomerContext(
        tenant_id=tenant_id,
        tenant_slug=tenant.slug,
        customer_id=customer.id,
        display_name=customer.name,
        grade=customer.grade,
        assurance=Assurance.LINK,
        link_id=link.id,
    )


def require_context(db: Session, raw: str | None) -> CustomerContext:
    context = resolve_context(db, raw, touch=True)
    if context is None:
        raise _unavailable()
    return context
