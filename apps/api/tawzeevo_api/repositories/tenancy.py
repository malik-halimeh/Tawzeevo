from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from tawzeevo_api.models import Tenant, TenantMembership, TenantRole, User


def all_tenant_ids(db: Session) -> list[UUID]:
    """Every tenant id, read from the global `tenants` table.

    `tenants` carries no `tenant_id` column, so it has no row-level policy: it is the one
    legitimate source a scheduled job may enumerate *before* a tenant scope is bound. Jobs use
    it to work tenant by tenant, binding `set_tenant_scope` before every scoped statement, so
    they find the same work whether the API connects with a role that bypasses row-level
    security or with the `NOSUPERUSER NOBYPASSRLS` role `docs/runbooks/database-role.md`
    prescribes. No cross-tenant read is possible through this list: it contains identifiers
    only, and every following statement runs inside one tenant's scope.
    """
    return list(db.scalars(select(Tenant.id).order_by(Tenant.id)))


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


def set_platform_scope(db: Session) -> None:
    """Bind platform-administration RLS paths (tenant applications) to the current transaction.

    Only the system-admin dependency binds this scope; it is transaction-local like the tenant
    and user scopes, so a commit drops it and any later read must restore it.
    """
    db.execute(text("SELECT set_config('app.platform_admin', 'true', true)"))


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
