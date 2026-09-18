from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import Tenant, TenantMembership, TenantRole, TenantStatus, User
from tawzeevo_api.repositories.tenancy import (
    commit_and_restore_tenant_scope,
    count_usable_owners,
    get_scoped_membership,
)
from tawzeevo_api.services.sync import revoke_membership_devices


def _user_for_update(db: Session, user_id: UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "User was not found")
    return user


def _tenant_for_update(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant was not found")
    return tenant


def _membership_identity(db: Session, tenant_id: UUID, membership_id: UUID) -> tuple[UUID, UUID]:
    membership = get_scoped_membership(
        db,
        tenant_id=tenant_id,
        membership_id=membership_id,
    )
    if membership is None:
        raise AppError(404, "TENANT_MEMBERSHIP_NOT_FOUND", "Tenant membership was not found")
    return membership.id, membership.user_id


def _membership_for_lifecycle_update(
    db: Session, tenant_id: UUID, membership_id: UUID
) -> tuple[Tenant, User, TenantMembership]:
    _, user_id = _membership_identity(db, tenant_id, membership_id)

    # Membership and user lifecycle changes take locks in the same user -> tenant order as
    # soft deletion. The tenant lock serializes concurrent last-owner decisions.
    user = _user_for_update(db, user_id)
    tenant = _tenant_for_update(db, tenant_id)
    membership = get_scoped_membership(
        db,
        tenant_id=tenant_id,
        membership_id=membership_id,
        for_update=True,
    )
    if membership is None:
        raise AppError(404, "TENANT_MEMBERSHIP_NOT_FOUND", "Tenant membership was not found")
    return tenant, user, membership


def _protect_last_active_owner(
    db: Session,
    tenant: Tenant,
    membership: TenantMembership,
    *,
    remains_active_owner: bool,
) -> None:
    if (
        tenant.status is TenantStatus.ACTIVE
        and membership.is_active
        and membership.role is TenantRole.OWNER
        and not remains_active_owner
        and count_usable_owners(db, tenant.id) <= 1
    ):
        db.rollback()
        raise AppError(
            409,
            "OWNER_TRANSFER_REQUIRED",
            "The membership is the last active owner of an active tenant",
        )


def create_membership(
    db: Session,
    tenant_id: UUID,
    user_id: UUID,
    role: TenantRole,
) -> TenantMembership:
    user = _user_for_update(db, user_id)
    if user.is_deleted:
        db.rollback()
        raise AppError(409, "MEMBERSHIP_USER_UNAVAILABLE", "A deleted user cannot be a member")
    _tenant_for_update(db, tenant_id)
    if get_scoped_membership(db, tenant_id=tenant_id, user_id=user_id) is not None:
        db.rollback()
        raise AppError(
            409,
            "TENANT_MEMBERSHIP_ALREADY_EXISTS",
            "A membership already exists for this user and tenant",
        )

    membership = TenantMembership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        is_active=True,
    )
    db.add(membership)
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "TENANT_MEMBERSHIP_ALREADY_EXISTS",
            "A membership already exists for this user and tenant",
        ) from exc
    db.refresh(membership)
    return membership


def reactivate_membership(db: Session, tenant_id: UUID, membership_id: UUID) -> TenantMembership:
    _, user, membership = _membership_for_lifecycle_update(db, tenant_id, membership_id)
    if user.is_deleted:
        db.rollback()
        raise AppError(409, "MEMBERSHIP_USER_UNAVAILABLE", "A deleted user cannot be a member")
    if membership.is_active:
        db.rollback()
        raise AppError(
            409,
            "TENANT_MEMBERSHIP_ALREADY_ACTIVE",
            "Tenant membership is already active",
        )

    membership.is_active = True
    membership.revoked_at = None
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(membership)
    return membership


def change_membership_role(
    db: Session,
    tenant_id: UUID,
    membership_id: UUID,
    role: TenantRole,
) -> TenantMembership:
    tenant, _, membership = _membership_for_lifecycle_update(db, tenant_id, membership_id)
    if membership.role is role:
        commit_and_restore_tenant_scope(db, tenant_id)
        db.refresh(membership)
        return membership

    _protect_last_active_owner(
        db,
        tenant,
        membership,
        remains_active_owner=membership.is_active and role is TenantRole.OWNER,
    )
    membership.role = role
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(membership)
    return membership


def revoke_membership(db: Session, tenant_id: UUID, membership_id: UUID) -> TenantMembership:
    tenant, _, membership = _membership_for_lifecycle_update(db, tenant_id, membership_id)
    if not membership.is_active:
        db.rollback()
        raise AppError(
            409,
            "TENANT_MEMBERSHIP_ALREADY_INACTIVE",
            "Tenant membership is already inactive",
        )

    _protect_last_active_owner(db, tenant, membership, remains_active_owner=False)
    membership.is_active = False
    membership.revoked_at = datetime.now(UTC)
    # PHASE_04.md J: a revoked membership loses its registered sync devices in the same transaction.
    revoke_membership_devices(db, tenant_id, membership.id, "MEMBERSHIP_REVOKED")
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(membership)
    return membership


def list_user_tenant_contexts(db: Session, user_id: UUID) -> list[tuple[TenantMembership, Tenant]]:
    return list(
        db.execute(
            select(TenantMembership, Tenant)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(
                TenantMembership.user_id == user_id,
                TenantMembership.is_active.is_(True),
            )
            .order_by(Tenant.name.asc(), Tenant.id.asc())
        ).tuples()
    )
