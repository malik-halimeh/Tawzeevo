from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.errors import AuthenticationError
from tawzeevo_api.models import AuthSession, User
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
