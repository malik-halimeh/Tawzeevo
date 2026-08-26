from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.schemas.platform import ReactivateTenantRequest
from tawzeevo_api.security import hash_password
from tawzeevo_api.services.memberships import (
    change_membership_role,
    create_membership,
    reactivate_membership,
    revoke_membership,
)
from tawzeevo_api.services.platform import reactivate_tenant

PASSWORD = "correct horse battery staple"


def _create_user(db: Session, email: str, *, deleted: bool = False) -> User:
    user = User(
        first_name="Tenant",
        last_name="Member",
        email=email,
        phone="+96170123456",
        city="Beirut",
        age=30,
        type=SystemUserType.CLIENT,
        password_hash=hash_password(PASSWORD),
        is_deleted=deleted,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(user)
    db.flush()
    return user


def _tenant_with_members(
    session_factory: sessionmaker[Session],
    *,
    status: TenantStatus = TenantStatus.ACTIVE,
    roles: tuple[TenantRole, ...] = (TenantRole.OWNER,),
) -> tuple[Tenant, list[User], list[TenantMembership]]:
    with session_factory() as db:
        tenant = Tenant(name="Membership tenant", status=status)
        db.add(tenant)
        db.flush()
        users = [
            _create_user(db, f"member-{tenant.id}-{index}@example.com")
            for index in range(len(roles))
        ]
        memberships = [
            TenantMembership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=role,
                is_active=True,
            )
            for user, role in zip(users, roles, strict=True)
        ]
        db.add_all(memberships)
        db.commit()
        for item in [tenant, *users, *memberships]:
            db.expunge(item)
        return tenant, users, memberships


def test_membership_create_revoke_reactivate_and_role_change_lifecycle(
    session_factory: sessionmaker[Session],
) -> None:
    tenant, _, _ = _tenant_with_members(session_factory)
    with session_factory() as db:
        driver = _create_user(db, "driver@example.com")
        db.commit()
        driver_id = driver.id

    with session_factory() as db:
        membership = create_membership(db, tenant.id, driver_id, TenantRole.DRIVER)
        assert membership.is_active is True
        assert membership.revoked_at is None

        with pytest.raises(AppError) as duplicate:
            create_membership(db, tenant.id, driver_id, TenantRole.DRIVER)
        assert duplicate.value.code == "TENANT_MEMBERSHIP_ALREADY_EXISTS"

        membership = change_membership_role(db, tenant.id, membership.id, TenantRole.OWNER)
        assert membership.role is TenantRole.OWNER

        membership = revoke_membership(db, tenant.id, membership.id)
        assert membership.is_active is False
        assert membership.revoked_at is not None

        membership = reactivate_membership(db, tenant.id, membership.id)
        assert membership.is_active is True
        assert membership.revoked_at is None


def test_membership_lookup_cannot_cross_tenant_scope(
    session_factory: sessionmaker[Session],
) -> None:
    first_tenant, _, _ = _tenant_with_members(session_factory)
    second_tenant, _, second_memberships = _tenant_with_members(session_factory)

    with session_factory() as db, pytest.raises(AppError) as denied:
        revoke_membership(db, first_tenant.id, second_memberships[0].id)

    assert first_tenant.id != second_tenant.id
    assert denied.value.code == "TENANT_MEMBERSHIP_NOT_FOUND"


@pytest.mark.parametrize("operation", ["revoke", "demote"])
def test_last_active_owner_change_is_rejected_without_partial_mutation(
    session_factory: sessionmaker[Session], operation: str
) -> None:
    tenant, _, memberships = _tenant_with_members(session_factory)
    membership_id = memberships[0].id

    with session_factory() as db, pytest.raises(AppError) as blocked:
        if operation == "revoke":
            revoke_membership(db, tenant.id, membership_id)
        else:
            change_membership_role(db, tenant.id, membership_id, TenantRole.DRIVER)

    assert blocked.value.code == "OWNER_TRANSFER_REQUIRED"
    with session_factory() as db:
        stored = db.get(TenantMembership, membership_id)
        assert stored is not None
        assert stored.is_active is True
        assert stored.role is TenantRole.OWNER
        assert stored.revoked_at is None


def test_second_owner_allows_membership_demotion(
    session_factory: sessionmaker[Session],
) -> None:
    tenant, _, memberships = _tenant_with_members(
        session_factory,
        roles=(TenantRole.OWNER, TenantRole.OWNER),
    )

    with session_factory() as db:
        changed = change_membership_role(
            db,
            tenant.id,
            memberships[0].id,
            TenantRole.DRIVER,
        )
        assert changed.role is TenantRole.DRIVER

    with session_factory() as db:
        active_owners = list(
            db.scalars(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == tenant.id,
                    TenantMembership.role == TenantRole.OWNER,
                    TenantMembership.is_active.is_(True),
                )
            )
        )
        assert len(active_owners) == 1


def test_concurrent_owner_revocations_cannot_orphan_active_tenant(
    session_factory: sessionmaker[Session],
) -> None:
    tenant, _, memberships = _tenant_with_members(
        session_factory,
        roles=(TenantRole.OWNER, TenantRole.OWNER),
    )

    def revoke(membership_id: object) -> str:
        with session_factory() as db:
            try:
                revoke_membership(db, tenant.id, membership_id)  # type: ignore[arg-type]
            except AppError as exc:
                return exc.code
        return "REVOKED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(revoke, [item.id for item in memberships]))

    assert sorted(results) == ["OWNER_TRANSFER_REQUIRED", "REVOKED"]
    with session_factory() as db:
        active_owners = list(
            db.scalars(
                select(TenantMembership)
                .join(User, User.id == TenantMembership.user_id)
                .where(
                    TenantMembership.tenant_id == tenant.id,
                    TenantMembership.role == TenantRole.OWNER,
                    TenantMembership.is_active.is_(True),
                    User.is_deleted.is_(False),
                )
            )
        )
        assert len(active_owners) == 1


def test_suspended_tenant_without_owner_cannot_reactivate(
    session_factory: sessionmaker[Session],
) -> None:
    tenant, users, memberships = _tenant_with_members(
        session_factory,
        status=TenantStatus.SUSPENDED,
    )
    with session_factory() as db:
        revoked = revoke_membership(db, tenant.id, memberships[0].id)
        assert revoked.is_active is False

    with session_factory() as db, pytest.raises(AppError) as blocked:
        actor = db.get(User, users[0].id)
        assert actor is not None
        reactivate_tenant(db, tenant.id, actor, ReactivateTenantRequest())

    assert blocked.value.code == "OWNER_TRANSFER_REQUIRED"
    with session_factory() as db:
        stored = db.get(Tenant, tenant.id)
        assert stored is not None and stored.status is TenantStatus.SUSPENDED


def test_deleted_user_cannot_join_or_reactivate_membership(
    session_factory: sessionmaker[Session],
) -> None:
    tenant, _, _ = _tenant_with_members(session_factory)
    with session_factory() as db:
        deleted_user = _create_user(db, "deleted@example.com", deleted=True)
        inactive_membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=deleted_user.id,
            role=TenantRole.DRIVER,
            is_active=False,
            revoked_at=datetime.now(UTC),
        )
        db.add(inactive_membership)
        db.commit()
        deleted_user_id = deleted_user.id
        inactive_membership_id = inactive_membership.id

    with session_factory() as db, pytest.raises(AppError) as create_blocked:
        create_membership(db, tenant.id, deleted_user_id, TenantRole.DRIVER)
    assert create_blocked.value.code == "MEMBERSHIP_USER_UNAVAILABLE"

    with session_factory() as db, pytest.raises(AppError) as reactivate_blocked:
        reactivate_membership(db, tenant.id, inactive_membership_id)
    assert reactivate_blocked.value.code == "MEMBERSHIP_USER_UNAVAILABLE"
