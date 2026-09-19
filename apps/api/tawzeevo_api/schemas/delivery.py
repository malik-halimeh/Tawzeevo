"""Delivery task API shapes (PHASE_07.md A/B/C/D/J; D-063)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from tawzeevo_api.models import ProductPriceBasis


class TaskCreateRequest(BaseModel):
    """A task for one CONFIRMED invoice. Without `assigned_membership_id` the task goes to the
    only eligible membership (the sole owner); with several eligible members the owner chooses."""

    model_config = ConfigDict(extra="forbid")

    invoice_id: UUID
    assigned_membership_id: UUID | None = None
    delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class TaskAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_membership_id: UUID
    expected_version: int = Field(ge=1)


class TaskCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=500)


class TaskCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class TaskUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


class AssigneeView(BaseModel):
    membership_id: UUID
    role: str
    display_name: str
    is_self: bool


class TaskLine(BaseModel):
    product_name: str
    quantity: Decimal
    price_basis: ProductPriceBasis
    pieces_per_box: int | None


class TaskResponse(BaseModel):
    """Owner view. The driver projection (P7-M2) is a strict subset built separately."""

    id: UUID
    status: str
    invoice_id: UUID
    official_invoice_number: str | None
    order_id: UUID | None
    customer_id: UUID
    customer_name: str
    customer_phone: str
    customer_address: str | None
    customer_latitude: Decimal | None
    customer_longitude: Decimal | None
    assignee: AssigneeView
    delivery_date: date | None
    route_sequence: int | None
    currency: str
    amount_to_collect: Decimal
    items: list[TaskLine]
    notes: str | None
    completed_at: datetime | None
    performed_by: AssigneeView | None
    completion_note: str | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    version: int
    created_at: datetime


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    eligible_members: list[AssigneeView]
    sole_operator: bool


class EligibleInvoice(BaseModel):
    invoice_id: UUID
    official_invoice_number: str | None
    customer_id: UUID
    customer_name: str
    currency: str
    net_sales: Decimal
    confirmed_at: datetime | None
    order_id: UUID | None
    delivery_date: date | None


class EligibleInvoiceListResponse(BaseModel):
    invoices: list[EligibleInvoice]
