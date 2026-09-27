from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from tawzeevo_api.config import get_settings
from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import get_current_user
from tawzeevo_api.models import User
from tawzeevo_api.schemas.push import (
    PushPublicKeyResponse,
    PushSubscribeRequest,
    PushSubscriptionState,
    PushUnsubscribeRequest,
)
from tawzeevo_api.services import push

push_router = APIRouter(prefix="/api/v1/push", tags=["push"])

Db = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@push_router.get("/public-key", response_model=PushPublicKeyResponse)
def public_key(_user: CurrentUser) -> PushPublicKeyResponse:
    """Whether phone notifications are available on this server, and the key to subscribe with
    (asked by a signed-in person only, right before turning notifications on)."""
    settings = get_settings()
    return PushPublicKeyResponse(
        enabled=settings.push_enabled,
        public_key=settings.vapid_public_key if settings.push_enabled else None,
    )


@push_router.post("/subscriptions", status_code=204)
def post_subscription(
    request: PushSubscribeRequest,
    db: Db,
    user: CurrentUser,
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
) -> Response:
    """Turn on notifications for this browser (the same endpoint again updates its keys)."""
    push.subscribe(db, user, request, user_agent)
    return Response(status_code=204)


@push_router.delete("/subscriptions", status_code=204)
def delete_subscription(request: PushUnsubscribeRequest, db: Db, user: CurrentUser) -> Response:
    push.unsubscribe(db, user, request.endpoint)
    return Response(status_code=204)


@push_router.post("/subscriptions/state", response_model=PushSubscriptionState)
def subscription_state(
    request: PushUnsubscribeRequest, db: Db, user: CurrentUser
) -> PushSubscriptionState:
    """Whether this browser's endpoint is on for the signed-in person."""
    return PushSubscriptionState(subscribed=push.is_subscribed(db, user, request.endpoint))
