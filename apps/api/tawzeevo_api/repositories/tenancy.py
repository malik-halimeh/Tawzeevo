from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tawzeevo_api.models import TenantMembership, TenantRole, User


def set_tenant_scope(db: Session, tenant_id: UUID) -> None:
    """Bind PostgreSQL RLS to one tenant for the current transaction."""
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def set_user_scope(db: Session, user_id: UUID) -> None:
    """Bind self-membership RLS reads to the authenticated user."""
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def commit_and_restore_tenant_scope(db: Session, tenant_id: UUID) -> None:
    """Commit a tenant mutation and restore scope for any post-commit reads."""
    db.commit()
    set_tenant_scope(db, tenant_id)


def get_scoped_membership(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID | None = None,
    membership_id: UUID | None = None,
    active_only: bool = False,
    for_update: bool = False,
) -> TenantMembership | None:
    if user_id is None and membership_id is None:
        raise ValueError("user_id or membership_id is required")

    set_tenant_scope(db, tenant_id)
    query = select(TenantMembership).where(TenantMembership.tenant_id == tenant_id)
    if user_id is not None:
        query = query.where(TenantMembership.user_id == user_id)
    if membership_id is not None:
        query = query.where(TenantMembership.id == membership_id)
    if active_only:
        query = query.where(TenantMembership.is_active.is_(True))
    if for_update:
        query = query.with_for_update()
    return db.scalar(query)


def count_usable_owners(db: Session, tenant_id: UUID) -> int:
    set_tenant_scope(db, tenant_id)
    return int(
        db.scalar(
            select(func.count())
            .select_from(TenantMembership)
            .join(User, User.id == TenantMembership.user_id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role == TenantRole.OWNER,
                TenantMembership.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )
        or 0
    )
