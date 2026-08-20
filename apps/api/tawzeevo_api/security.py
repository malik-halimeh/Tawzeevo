from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.models import AuthSession, User

JWT_ALGORITHM = "HS256"
PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("invalid-password-placeholder")


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASH.verify(password, password_hash)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    user: User,
    auth_session: AuthSession,
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> str:
    active_settings = settings or get_settings()
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=active_settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "sid": str(auth_session.id),
        "sv": user.security_version,
        "type": "access",
        "jti": str(uuid4()),
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "iss": active_settings.jwt_issuer,
        "aud": active_settings.jwt_audience,
    }
    return jwt.encode(payload, active_settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    active_settings = settings or get_settings()
    payload: dict[str, Any] = jwt.decode(
        token,
        active_settings.jwt_secret,
        algorithms=[JWT_ALGORITHM],
        audience=active_settings.jwt_audience,
        issuer=active_settings.jwt_issuer,
        options={"require": ["sub", "sid", "sv", "type", "jti", "iat", "nbf", "exp"]},
    )
    return payload
