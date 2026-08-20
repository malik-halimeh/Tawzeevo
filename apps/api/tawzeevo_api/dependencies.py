from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.errors import AppError, AuthenticationError
from tawzeevo_api.models import (
    AuthSession,
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


class AccessClaims(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sub: UUID
    sid: UUID
    sv: int
    type: str


@dataclass(frozen=True)
class AuthContext:
    user: User
    auth_session: AuthSession


@dataclass(frozen=True)
class TenantContext:
    tenant: Tenant
    membership: TenantMembership


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError()
    try:
        payload = decode_access_token(credentials.credentials)
        claims = AccessClaims.model_validate(payload)
    except (jwt.InvalidTokenError, ValidationError, ValueError, TypeError) as exc:
        raise AuthenticationError() from exc

    if claims.type != "access":
        raise AuthenticationError()

    auth_session = db.get(AuthSession, claims.sid)
    if auth_session is None:
        raise AuthenticationError()
    user = db.get(User, claims.sub)
    now = datetime.now(UTC)
    if (
        user is None
        or user.id != auth_session.user_id
        or user.is_deleted
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or claims.sv != user.security_version
        or auth_session.security_version != user.security_version
    ):
        raise AuthenticationError()
    return AuthContext(user=user, auth_session=auth_session)


def get_current_user(context: Annotated[AuthContext, Depends(get_auth_context)]) -> User:
    return context.user


def require_system_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.type is not SystemUserType.ADMIN:
        raise AppError(403, "ADMIN_REQUIRED", "System administrator access is required")
    return user


def require_client(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.type is not SystemUserType.CLIENT:
        raise AppError(403, "CLIENT_REQUIRED", "Client access is required")
    return user


def resolve_tenant_context(db: Session, user: User, tenant_id: UUID) -> TenantContext:
    db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    membership = db.scalar(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user.id,
            TenantMembership.is_active.is_(True),
        )
    )
    if membership is None:
        raise AppError(403, "TENANT_MEMBERSHIP_REQUIRED", "Active tenant membership is required")
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant was not found")
    if tenant.status is TenantStatus.SUSPENDED:
        raise AppError(403, "TENANT_SUSPENDED", "Tenant business access is suspended")
    if tenant.status is TenantStatus.CLOSED:
        raise AppError(403, "TENANT_CLOSED", "Tenant business access is closed")
    return TenantContext(tenant=tenant, membership=membership)


def get_tenant_context(
    tenant_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TenantContext:
    return resolve_tenant_context(db, user, tenant_id)


def require_tenant_owner(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    if context.membership.role is not TenantRole.OWNER:
        raise AppError(403, "TENANT_OWNER_REQUIRED", "Tenant owner access is required")
    return context
