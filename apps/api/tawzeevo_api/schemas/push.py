from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PushPublicKeyResponse(BaseModel):
    enabled: bool
    public_key: str | None


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="ignore")

    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscribeRequest(BaseModel):
    """The browser's PushSubscription JSON, plus the business on screen (optional)."""

    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=10, max_length=1000, pattern=r"^https://")
    keys: PushKeys
    tenant_id: UUID | None = None


class PushUnsubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=10, max_length=1000)


class PushSubscriptionState(BaseModel):
    subscribed: bool
