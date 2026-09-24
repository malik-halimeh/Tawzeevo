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

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Customer,
    CustomerAccessLink,
    CustomerGrade,
    CustomerVerifiedSession,
    Tenant,
    TenantStatus,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.services.otp_delivery import delivery_is_usable

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


# LINK (Phase 5) and VERIFIED (Phase 9 P9-M5) can be enforced; ACCOUNT_REQUIRED waits for P9-M6.
AVAILABLE_POLICIES = frozenset({AccessPolicy.LINK, AccessPolicy.VERIFIED})
_ASSURANCE_RANK = {
    Assurance.ANONYMOUS: 0,
    Assurance.LINK: 1,
    Assurance.VERIFIED: 2,
    Assurance.ACCOUNT: 3,
}
_POLICY_RANK = {AccessPolicy.LINK: 1, AccessPolicy.VERIFIED: 2, AccessPolicy.ACCOUNT_REQUIRED: 3}
SESSION_HEADER = "X-Customer-Session"


def satisfies(assurance: Assurance, policy: AccessPolicy) -> bool:
    return _ASSURANCE_RANK[assurance] >= _POLICY_RANK[policy]


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
    required_policy: AccessPolicy = AccessPolicy.LINK
    phone: str = ""  # the customer's own number, for the verification challenge only
    # Whether an address is on file; never the address itself (D-090 limited disclosure).
    has_saved_address: bool = False

    @property
    def granted(self) -> bool:
        """Personalized pricing and order submission are granted only when the assurance the
        visitor holds satisfies the policy that applies to this customer (D-072)."""
        return satisfies(self.assurance, self.required_policy)

    @property
    def contact_hint(self) -> str:
        return f"…{self.phone[-3:]}" if self.phone else ""


def _unavailable() -> AppError:
    # Constant failure: never reveals whether a customer, link or business exists.
    return AppError(404, "CUSTOMER_LINK_UNAVAILABLE", "This link is not available")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def effective_policy(tenant: Tenant, customer: Customer) -> AccessPolicy:
    override = customer.access_policy_override
    return AccessPolicy(override) if override else AccessPolicy(tenant.customer_access_policy)


def selectable_policies() -> frozenset[AccessPolicy]:
    """Policies an owner may select right now: VERIFIED needs a usable one-time-code delivery
    (otherwise a business would lock its customers out of verification)."""
    if delivery_is_usable():
        return AVAILABLE_POLICIES
    return AVAILABLE_POLICIES - {AccessPolicy.VERIFIED}


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
    if policy not in selectable_policies():
        raise AppError(
            409,
            "OTP_PROVIDER_NOT_CONFIGURED",
            "VERIFIED needs a configured one-time-code delivery provider",
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


def revoke_sessions_for_link(db: Session, tenant_id: UUID, link_id: UUID, reason: str) -> None:
    db.execute(
        update(CustomerVerifiedSession)
        .where(
            CustomerVerifiedSession.tenant_id == tenant_id,
            CustomerVerifiedSession.link_id == link_id,
            CustomerVerifiedSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
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
        revoke_sessions_for_link(db, tenant_id, previous.id, "link_rotated")
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
    revoke_sessions_for_link(db, tenant_id, link.id, "link_revoked")
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


def _session_assurance(
    db: Session, tenant_id: UUID, link: CustomerAccessLink, session_raw: str | None
) -> Assurance:
    """VERIFIED when a live verified session for this very link is presented, else LINK."""
    if not session_raw or not TOKEN_PATTERN.fullmatch(session_raw):
        return Assurance.LINK
    now = datetime.now(UTC)
    row = db.scalar(
        select(CustomerVerifiedSession).where(
            CustomerVerifiedSession.tenant_id == tenant_id,
            CustomerVerifiedSession.token_sha256 == _hash(session_raw),
            CustomerVerifiedSession.link_id == link.id,
            CustomerVerifiedSession.revoked_at.is_(None),
            CustomerVerifiedSession.expires_at > now,
        )
    )
    if row is None or row.customer_id != link.customer_id:
        return Assurance.LINK
    row.last_used_at = now
    return Assurance.VERIFIED


def resolve_state(
    db: Session, raw: str | None, session_raw: str | None = None, *, touch: bool = False
) -> CustomerContext | None:
    """Resolve a capability (and an optional verified session) to the visitor's full state:
    who the link is for, which policy applies and which assurance is held. None for anything
    that is not a live link of an ACTIVE business. Never raises for a bad secret (D-072)."""
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
    if customer is None:
        return None
    policy = effective_policy(tenant, customer)
    if policy is AccessPolicy.ACCOUNT_REQUIRED:
        return None  # P9-M6
    assurance = _session_assurance(db, tenant_id, link, session_raw)
    if touch:
        link.last_used_at = now
    if touch or assurance is Assurance.VERIFIED:
        commit_and_restore_tenant_scope(db, tenant_id)
    return CustomerContext(
        tenant_id=tenant_id,
        tenant_slug=tenant.slug,
        customer_id=customer.id,
        display_name=customer.name,
        grade=customer.grade,
        assurance=assurance,
        link_id=link.id,
        required_policy=policy,
        phone=customer.phone,
        has_saved_address=bool((customer.address or "").strip()),
    )


def resolve_context(
    db: Session, raw: str | None, session_raw: str | None = None, *, touch: bool = False
) -> CustomerContext | None:
    """The granted context only: personalized pricing and checkout see a customer solely when
    the held assurance satisfies the policy; an unmet policy is the anonymous storefront."""
    state = resolve_state(db, raw, session_raw, touch=touch)
    return state if state is not None and state.granted else None


def require_context(
    db: Session, raw: str | None, session_raw: str | None = None
) -> CustomerContext:
    """Full state for the storefront's context call (it needs to know when verification is
    still required); every other consumer uses `resolve_context`."""
    context = resolve_state(db, raw, session_raw, touch=True)
    if context is None:
        raise _unavailable()
    return context
