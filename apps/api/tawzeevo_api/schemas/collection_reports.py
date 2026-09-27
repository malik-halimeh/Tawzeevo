from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CollectionClaim(BaseModel):
    """What the driver says at completion: paid in full, paid partly (amount required), not paid."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["FULL", "PARTIAL", "NONE"]
    amount: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=4)
    idempotency_key: UUID | None = None

    @model_validator(mode="after")
    def amount_only_for_partial(self) -> Self:
        if self.kind == "PARTIAL" and self.amount is None:
            raise ValueError("amount is required when paid partly")
        if self.kind != "PARTIAL" and self.amount is not None:
            raise ValueError("amount is only given when paid partly")
        return self


class CollectionRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class CollectionReportResponse(BaseModel):
    id: UUID
    status: str
    kind: str
    amount: Decimal | None
    currency: str
    task_id: UUID
    invoice_id: UUID
    official_invoice_number: str | None
    customer_id: UUID
    customer_name: str
    reporter_name: str
    confirmed_payment_id: UUID | None
    reason: str | None
    created_at: datetime
    decided_at: datetime | None


class CollectionReportListResponse(BaseModel):
    reports: list[CollectionReportResponse]


class CustomerNotificationResponse(BaseModel):
    id: UUID
    kind: str
    data: dict[str, str]
    created_at: datetime
    read: bool


class CustomerNotificationListResponse(BaseModel):
    unread: int
    notifications: list[CustomerNotificationResponse]
