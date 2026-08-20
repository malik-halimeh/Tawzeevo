from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.errors import AppError, AuthenticationError
from tawzeevo_api.models import AuthSession, SystemUserType, User
from tawzeevo_api.phone import normalize_phone
from tawzeevo_api.repositories.auth import (
    get_session_by_refresh_hash_for_update,
    get_session_for_update,
    get_user_by_email,
    revoke_active_user_sessions,
)
from tawzeevo_api.schemas.auth import LoginRequest, RegisterRequest
from tawzeevo_api.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str


def register_client(db: Session, request: RegisterRequest) -> User:
    email = str(request.email)
    if get_user_by_email(db, email) is not None:
        raise AppError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists")

    user = User(
        first_name=request.first_name,
        last_name=request.last_name,
        email=email,
        phone=normalize_phone(request.phone),
        phone_raw=request.phone,
        city=request.city,
        age=request.age,
        type=SystemUserType.CLIENT,
        password_hash=hash_password(request.password.get_secret_value()),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists"
        ) from exc
    db.refresh(user)
    return user


def _create_session(
    db: Session, user: User, now: datetime, settings: Settings
) -> tuple[AuthSession, str]:
    refresh_token = generate_refresh_token()
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        security_version=user.security_version,
        expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(auth_session)
    db.flush()
    return auth_session, refresh_token


def login(db: Session, request: LoginRequest, settings: Settings | None = None) -> IssuedTokens:
    active_settings = settings or get_settings()
    user = get_user_by_email(db, str(request.email))
    password = request.password.get_secret_value()

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise AuthenticationError("INVALID_CREDENTIALS", "Email or password is incorrect")
    if not verify_password(password, user.password_hash) or user.is_deleted:
        raise AuthenticationError("INVALID_CREDENTIALS", "Email or password is incorrect")

    now = datetime.now(UTC)
    auth_session, refresh_token = _create_session(db, user, now, active_settings)
    access_token = create_access_token(user, auth_session, now=now, settings=active_settings)
    db.commit()
    return IssuedTokens(access_token=access_token, refresh_token=refresh_token)


def rotate_refresh_token(
    db: Session, refresh_token: str, settings: Settings | None = None
) -> IssuedTokens:
    active_settings = settings or get_settings()
    now = datetime.now(UTC)
    auth_session = get_session_by_refresh_hash_for_update(db, hash_refresh_token(refresh_token))
    if auth_session is None:
        raise AuthenticationError()

    user = db.get(User, auth_session.user_id)
    if auth_session.revoked_at is not None:
        if auth_session.revoke_reason == "ROTATED" and user is not None:
            revoke_active_user_sessions(db, user.id, now, "ROTATED_TOKEN_REUSE")
            db.commit()
        raise AuthenticationError("REFRESH_TOKEN_REUSED", "Refresh token reuse was detected")

    if auth_session.expires_at <= now:
        auth_session.revoked_at = now
        auth_session.revoke_reason = "EXPIRED"
        db.commit()
        raise AuthenticationError()

    if user is None or user.is_deleted or user.security_version != auth_session.security_version:
        auth_session.revoked_at = now
        auth_session.revoke_reason = "USER_INVALID"
        db.commit()
        raise AuthenticationError()

    replacement, replacement_token = _create_session(db, user, now, active_settings)
    auth_session.revoked_at = now
    auth_session.revoke_reason = "ROTATED"
    auth_session.last_used_at = now
    auth_session.replaced_by_session_id = replacement.id
    access_token = create_access_token(user, replacement, now=now, settings=active_settings)
    db.commit()
    return IssuedTokens(access_token=access_token, refresh_token=replacement_token)


def logout(db: Session, auth_session: AuthSession) -> None:
    locked_session = get_session_for_update(db, auth_session.id)
    if locked_session is not None and locked_session.revoked_at is None:
        locked_session.revoked_at = datetime.now(UTC)
        locked_session.revoke_reason = "LOGOUT"
    db.commit()
