from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from tawzeevo_api.models import AuthSession, User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_session_by_refresh_hash_for_update(
    db: Session, refresh_token_hash: str
) -> AuthSession | None:
    statement: Select[tuple[AuthSession]] = (
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == refresh_token_hash)
        .with_for_update()
    )
    return db.scalar(statement)


def get_session_for_update(db: Session, session_id: UUID) -> AuthSession | None:
    return db.scalar(select(AuthSession).where(AuthSession.id == session_id).with_for_update())


def revoke_active_user_sessions(
    db: Session, user_id: UUID, revoked_at: datetime, reason: str
) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=revoked_at, revoke_reason=reason)
    )
