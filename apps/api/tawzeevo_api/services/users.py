from __future__ import annotations

import math
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuthSession,
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.phone import normalize_phone
from tawzeevo_api.repositories.auth import get_user_by_email, revoke_active_user_sessions
from tawzeevo_api.schemas.users import AdminCreateUserRequest, ProfileUpdateRequest
from tawzeevo_api.security import hash_password


def _email_conflicts(db: Session, email: str, user_id: UUID | None = None) -> bool:
    existing = get_user_by_email(db, email)
    return existing is not None and existing.id != user_id


def _commit_user(db: Session, user: User) -> User:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists"
        ) from exc
    db.refresh(user)
    return user


def create_user(db: Session, request: AdminCreateUserRequest) -> User:
    email = str(request.email)
    if _email_conflicts(db, email):
        raise AppError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists")
    user = User(
        first_name=request.first_name,
        last_name=request.last_name,
        email=email,
        phone=normalize_phone(request.phone),
        phone_raw=request.phone,
        city=request.city,
        age=request.age,
        type=request.type,
        password_hash=hash_password(request.password.get_secret_value()),
    )
    db.add(user)
    return _commit_user(db, user)


def update_user_profile(
    db: Session,
    user: User,
    request: ProfileUpdateRequest,
    *,
    allow_role_change: bool = False,
) -> User:
    values = request.model_dump(exclude_unset=True, exclude={"password", "type"})
    email_value = values.get("email")
    if email_value is not None:
        email = str(email_value)
        if _email_conflicts(db, email, user.id):
            raise AppError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists")
        values["email"] = email
    phone_value = values.get("phone")
    if phone_value is not None:
        raw_phone = str(phone_value)
        values["phone"] = normalize_phone(raw_phone)
        user.phone_raw = raw_phone
    for field_name, value in values.items():
        setattr(user, field_name, value)

    security_changed = False
    if request.password is not None:
        user.password_hash = hash_password(request.password.get_secret_value())
        security_changed = True
    requested_type = getattr(request, "type", None)
    if allow_role_change and requested_type is not None and requested_type != user.type:
        user.type = requested_type
        security_changed = True
    if security_changed:
        user.security_version += 1
        revoke_active_user_sessions(db, user.id, datetime.now(UTC), "USER_SECURITY_UPDATED")
    return _commit_user(db, user)


def get_user_for_update(db: Session, user_id: UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError(404, "USER_NOT_FOUND", "User was not found")
    return user


def list_users(
    db: Session,
    *,
    page: int,
    limit: int,
    age: int | None,
    city: str | None,
    system_type: SystemUserType | None,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    search: str | None,
) -> tuple[list[User], int, int]:
    conditions: list[ColumnElement[bool]] = [User.is_deleted.is_(False)]
    exact_text_filters = (
        (User.city, city),
        (User.first_name, first_name),
        (User.last_name, last_name),
        (User.email, email),
    )
    for column, value in exact_text_filters:
        if value is not None:
            normalized_value = unicodedata.normalize("NFC", value).strip().lower()
            conditions.append(func.lower(column) == normalized_value)
    if age is not None:
        conditions.append(User.age == age)
    if system_type is not None:
        conditions.append(User.type == system_type)
    if search is not None and search.strip():
        term = f"%{unicodedata.normalize('NFC', search).strip().lower()}%"
        conditions.append(
            or_(
                func.lower(User.first_name).like(term),
                func.lower(User.last_name).like(term),
                func.lower(User.email).like(term),
            )
        )

    total = int(db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0)
    users = list(
        db.scalars(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.asc(), User.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return users, total, math.ceil(total / limit) if total else 0


def _set_tenant_scope(db: Session, tenant_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def soft_delete_user(db: Session, user_id: UUID) -> None:
    user = get_user_for_update(db, user_id)
    if user.is_deleted:
        raise AppError(404, "USER_NOT_FOUND", "User was not found")

    tenants = list(db.scalars(select(Tenant).order_by(Tenant.id).with_for_update()))
    active_membership_tenants: list[UUID] = []
    for tenant in tenants:
        _set_tenant_scope(db, tenant.id)
        membership = db.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.user_id == user.id,
                TenantMembership.is_active.is_(True),
            )
        )
        if membership is None:
            continue
        active_membership_tenants.append(tenant.id)
        if tenant.status is not TenantStatus.ACTIVE or membership.role is not TenantRole.OWNER:
            continue
        usable_owner_count = int(
            db.scalar(
                select(func.count())
                .select_from(TenantMembership)
                .join(User, User.id == TenantMembership.user_id)
                .where(
                    TenantMembership.tenant_id == tenant.id,
                    TenantMembership.role == TenantRole.OWNER,
                    TenantMembership.is_active.is_(True),
                    User.is_deleted.is_(False),
                )
            )
            or 0
        )
        if usable_owner_count <= 1:
            db.rollback()
            raise AppError(
                409,
                "OWNER_TRANSFER_REQUIRED",
                "The user is the last active owner of an active tenant",
            )

    now = datetime.now(UTC)
    for tenant_id in active_membership_tenants:
        _set_tenant_scope(db, tenant_id)
        db.execute(
            update(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user.id,
                TenantMembership.is_active.is_(True),
            )
            .values(is_active=False, revoked_at=now)
        )
    user.is_deleted = True
    user.deleted_at = now
    user.security_version += 1
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="USER_DELETED")
    )
    db.commit()


def user_count(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(User).where(User.is_deleted.is_(False))) or 0
    )


def average_user_age(db: Session) -> float | None:
    value = db.scalar(select(func.avg(User.age)).where(User.is_deleted.is_(False)))
    return float(value) if value is not None else None


def top_user_cities(db: Session) -> list[dict[str, str | int]]:
    normalized_city = func.lower(User.city).label("normalized_city")
    rows = db.execute(
        select(
            func.initcap(normalized_city).label("city"),
            func.count().label("count"),
            normalized_city,
        )
        .where(User.is_deleted.is_(False))
        .group_by(normalized_city)
        .order_by(func.count().desc(), normalized_city.asc())
        .limit(3)
    )
    return [
        {"city": str(row._mapping["city"]), "count": int(row._mapping["count"])} for row in rows
    ]
