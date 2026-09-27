from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PickupReportLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procurement_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    unit_cost: Decimal = Field(ge=0, max_digits=20, decimal_places=4)


class PickupReportCreateRequest(BaseModel):
    """What the runner picked up from one supplier for one list; a retry with the same key returns
    the same report."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    list_id: UUID
    supplier_id: UUID
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    notes: str | None = Field(default=None, max_length=500)
    lines: list[PickupReportLineRequest] = Field(min_length=1, max_length=200)


class PickupReportRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class PickupReportLine(BaseModel):
    procurement_item_id: UUID
    product_id: UUID
    product_name: str
    quantity: Decimal
    unit_cost: Decimal


class PickupReportResponse(BaseModel):
    id: UUID
    status: str
    list_id: UUID
    list_title: str
    supplier_id: UUID
    supplier_name: str
    reporter_name: str
    currency: str
    total: Decimal
    notes: str | None
    lines: list[PickupReportLine]
    confirmed_purchase_id: UUID | None
    reason: str | None
    created_at: datetime
    decided_at: datetime | None


class PickupReportListResponse(BaseModel):
    reports: list[PickupReportResponse]
