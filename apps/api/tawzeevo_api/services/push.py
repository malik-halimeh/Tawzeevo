"""Web push to installed phones (D-116).

Subscriptions belong to a person. The sender runs after the request's commit (a background task),
with its own session and a timeout of at most five seconds per message; a 404 or 410 from the push
service removes the subscription, other failures are counted and logged, and nothing is sent when
push is not configured. Payloads carry a title, a short line and an address only: no amounts,
no customer details."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import SessionLocal
from tawzeevo_api.models import (
    PushSubscription,
    Tenant,
    TenantMembership,
    TenantRole,
    User,
)
from tawzeevo_api.repositories.tenancy import set_tenant_scope, set_user_scope
from tawzeevo_api.schemas.push import PushSubscribeRequest

logger = logging.getLogger(__name__)

# The session used by the sender (tests point it at their own database).
SESSION_FACTORY: Callable[[], Session] = SessionLocal


def _send(subscription: dict[str, Any], payload: str) -> None:
    """One message through pywebpush (MPL-2.0, used unmodified)."""
    from pywebpush import webpush  # type: ignore[import-untyped]

    settings = get_settings()
    webpush(
        subscription_info=subscription,
        data=payload,
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject or ""},
        timeout=settings.push_timeout_seconds,
    )


# ---------- the person's own subscriptions ----------


def subscribe(
    db: Session, user: User, request: PushSubscribeRequest, user_agent: str | None
) -> None:
    set_user_scope(db, user.id)
    row = db.scalar(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id, PushSubscription.endpoint == request.endpoint
        )
    )
    if row is None:
        row = PushSubscription(user_id=user.id, endpoint=request.endpoint)
        db.add(row)
    row.p256dh = request.keys.p256dh
    row.auth = request.keys.auth
    row.tenant_id = request.tenant_id
    row.user_agent = (user_agent or "")[:300] or None
    row.failure_count = 0
    db.commit()


def unsubscribe(db: Session, user: User, endpoint: str) -> None:
    """Only the caller's own subscription is removed; another person's endpoint is untouched."""
    set_user_scope(db, user.id)
    db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id, PushSubscription.endpoint == endpoint
        )
    )
    db.commit()


def is_subscribed(db: Session, user: User, endpoint: str) -> bool:
    set_user_scope(db, user.id)
    return (
        db.scalar(
            select(PushSubscription.id).where(
                PushSubscription.user_id == user.id, PushSubscription.endpoint == endpoint
            )
        )
        is not None
    )


# ---------- sending (after commit) ----------


def notify_users(user_ids: Iterable[UUID], title: str, body: str, url: str) -> int:
    """Send to every subscription of these people. Returns the number delivered."""
    if not get_settings().push_enabled:
        return 0
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    # Read the subscriptions, then give the database connection back before talking to the push
    # services (up to 5 s each): a pooled connection is never held while waiting on the network.
    with SESSION_FACTORY() as db:
        db.execute(text("SELECT set_config('app.push_delivery', 'true', true)"))
        targets = [
            (row.id, {"endpoint": row.endpoint, "keys": {"p256dh": row.p256dh, "auth": row.auth}})
            for row in db.scalars(select(PushSubscription).where(PushSubscription.user_id.in_(ids)))
        ]
    # None = delivered; otherwise the push service's failure status (0 when unknown).
    outcomes: dict[UUID, int | None] = {}
    for subscription_id, info in targets:
        try:
            _send(info, payload)
        except Exception as exc:  # noqa: BLE001 - every failure is handled below
            status = getattr(getattr(exc, "response", None), "status_code", None)
            outcomes[subscription_id] = status if isinstance(status, int) else 0
            if status in (404, 410):
                logger.info("push subscription gone (status=%s); removed", status)
            else:
                logger.warning("push send failed (status=%s): %s", status, type(exc).__name__)
            continue
        outcomes[subscription_id] = None
    if not outcomes:
        return 0
    delivered = 0
    with SESSION_FACTORY() as db:
        db.execute(text("SELECT set_config('app.push_delivery', 'true', true)"))
        rows = db.scalars(select(PushSubscription).where(PushSubscription.id.in_(list(outcomes))))
        for row in rows:
            status = outcomes[row.id]
            if status in (404, 410):
                db.delete(row)
            elif status is not None:
                row.failure_count += 1
                row.last_failure_at = datetime.now(UTC)
            else:
                row.last_success_at = datetime.now(UTC)
                row.failure_count = 0
                delivered += 1
        db.commit()
    return delivered


def _owner_user_ids(db: Session, tenant_id: UUID) -> list[UUID]:
    set_tenant_scope(db, tenant_id)
    return list(
        db.scalars(
            select(TenantMembership.user_id).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.role == TenantRole.OWNER,
                TenantMembership.is_active.is_(True),
            )
        )
    )


def notify_owners(tenant_id: UUID, title: str, body: str, url: str) -> int:
    """The active owners of one business only."""
    if not get_settings().push_enabled:
        return 0
    with SESSION_FACTORY() as db:
        owners = _owner_user_ids(db, tenant_id)
    return notify_users(owners, title, body, url)


def notify_owners_of_shop(slug: str, title: str, body: str, url_path: str) -> int:
    if not get_settings().push_enabled:
        return 0
    with SESSION_FACTORY() as db:
        tenant_id = db.scalar(select(Tenant.id).where(Tenant.slug == slug))
    if tenant_id is None:
        return 0
    return notify_owners(tenant_id, title, body, f"{url_path}{tenant_id}")


def notify_membership(tenant_id: UUID, membership_id: UUID, title: str, body: str, url: str) -> int:
    """One member (a driver just assigned a delivery)."""
    if not get_settings().push_enabled:
        return 0
    with SESSION_FACTORY() as db:
        set_tenant_scope(db, tenant_id)
        user_id = db.scalar(
            select(TenantMembership.user_id).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.id == membership_id,
                TenantMembership.is_active.is_(True),
            )
        )
    return notify_users([user_id] if user_id else [], title, body, url)


# Messages: a title and a short line in both languages, and where to go. Never amounts or names.
NEW_ORDER = ("New order · طلب جديد", "A customer placed an order. · وصل طلب من عميل.")
COLLECTION = (
    "Payment to confirm · دفعة للتأكيد",
    "A driver reported a payment at a delivery. · أبلغ سائق عن دفعة عند التسليم.",
)
PICKUP = (
    "Pickup to confirm · استلام للتأكيد",
    "A pickup from a supplier was reported. · أُبلغ عن استلام من مورّد.",
)
ASSIGNED = ("New delivery · توصيل جديد", "A delivery was assigned to you. · أُسند إليك توصيل.")


def workspace(tenant_id: UUID, section: str) -> str:
    return (
        f"/workspace?tenant={tenant_id}&section={section}"
        if section != "work"
        else (f"/workspace?tenant={tenant_id}")
    )
