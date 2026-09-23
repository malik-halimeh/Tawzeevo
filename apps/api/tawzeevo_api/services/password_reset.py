"""Password recovery (PHASE_09.md C, D-077): forgot → one-time token by e-mail → reset.

Properties enforced here: token stored as a hash only; short expiry; single use; earlier unused
tokens of the same user die when a new one is issued; the response to "forgot" is identical
whether or not the address exists; a completed reset bumps the security version so every
session and access token is invalid; audit events carry no token and no e-mail address."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tawzeevo_api import metrics
from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import AuditEvent, PasswordResetToken, User
from tawzeevo_api.repositories.auth import get_user_by_email, revoke_active_user_sessions
from tawzeevo_api.security import hash_password
from tawzeevo_api.services.mailer import Mail, MailerError, get_mailer

_TOKEN_BYTES = 32
logger = logging.getLogger("tawzeevo.auth")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _message(link: str, minutes: int) -> Mail:
    text = (
        "Someone asked to reset the password of your Tawzeevo account. If it was you, open this "
        f"link within {minutes} minutes:\n\n{link}\n\nIf it was not you, ignore this message; "
        "your password stays as it is.\n\n"
        "طُلب إعادة تعيين كلمة مرور حسابك في توزيعو. إن كنت أنت من طلب ذلك فافتح الرابط أعلاه "
        f"خلال {minutes} دقيقة. وإن لم تكن أنت فتجاهل هذه الرسالة؛ كلمة مرورك تبقى كما هي."
    )
    return Mail(to="", subject="Tawzeevo password reset / إعادة تعيين كلمة المرور", text=text)


def request_reset(db: Session, email: str, settings: Settings | None = None) -> None:
    """Always returns; an unknown or deleted address produces no observable difference."""
    active = settings or get_settings()
    user = get_user_by_email(db, email)
    if user is None or user.is_deleted:
        return
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)  # only the newest link works
    )
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_sha256=_hash(token),
            expires_at=now + timedelta(minutes=active.password_reset_ttl_minutes),
        )
    )
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="password_reset_requested",
            entity_type="user",
            entity_id=user.id,
            details={},
        )
    )
    db.commit()
    link = f"{active.password_reset_url.rstrip('/')}#{token}"  # fragment: never in referrers/logs
    mail = _message(link, active.password_reset_ttl_minutes)
    try:
        get_mailer(active).send(Mail(to=user.email, subject=mail.subject, text=mail.text))
    except MailerError as exc:
        # The token exists but the holder cannot receive it. The answer stays the same 202 as for
        # an unknown address (a distinct error would reveal that the address is registered); the
        # outage is counted for the alert probe and logged without the address or the token.
        metrics.increment("mail_failures")
        logger.warning("password reset mail could not be delivered: %s", type(exc).__name__)


def reset_password(db: Session, token: str, new_password: str) -> UUID:
    now = datetime.now(UTC)
    row = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_sha256 == _hash(token))
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise AppError(400, "RESET_TOKEN_INVALID", "This reset link is invalid or has expired")
    user = db.get(User, row.user_id)
    if user is None or user.is_deleted:
        raise AppError(400, "RESET_TOKEN_INVALID", "This reset link is invalid or has expired")
    row.used_at = now
    user.password_hash = hash_password(new_password)
    user.security_version += 1  # every access token and session dies with the old password
    revoke_active_user_sessions(db, user.id, now, "PASSWORD_RESET")
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            action="password_reset_completed",
            entity_type="user",
            entity_id=user.id,
            details={"sessions_revoked": True},
        )
    )
    db.commit()
    return user.id
