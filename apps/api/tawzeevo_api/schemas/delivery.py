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


class MyWorkTask(BaseModel):
    """Least-privilege projection (PHASE_07.md D): only what the assigned member needs to deliver
    and collect. No costs, margins, other customers, settings or other members' tasks."""

    id: UUID
    status: str
    official_invoice_number: str | None
    customer_name: str
    customer_phone: str
    customer_address: str | None
    customer_latitude: Decimal | None
    customer_longitude: Decimal | None
    delivery_date: date | None
    route_sequence: int | None
    currency: str
    amount_to_collect: Decimal
    items: list[TaskLine]
    notes: str | None
    version: int


class MyWorkResponse(BaseModel):
    tasks: list[MyWorkTask]
    membership_id: UUID
    role: str


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=10, decimal_places=6)


class LocationUpdateRequest(Coordinates):
    """A new reading for the task's customer (PHASE_07.md E; D-061)."""

    source: str = Field(pattern=r"^(gps|manual|geocoded)$")
    accuracy_meters: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    confirm: bool = False


class LocationView(BaseModel):
    latitude: Decimal | None
    longitude: Decimal | None
    source: str | None
    captured_at: datetime | None
    accuracy_meters: Decimal | None
    confirmed_at: datetime | None


class LocationUpdateResponse(BaseModel):
    applied: bool
    reason: str
    location: LocationView


class SuggestOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Coordinates | None = None
    task_ids: list[UUID] = Field(min_length=1, max_length=200)
    allow_online: bool = True


class SuggestedStop(BaseModel):
    task_id: UUID
    sequence: int
    customer_name: str
    latitude: Decimal | None
    longitude: Decimal | None
    has_location: bool


class SuggestOrderResponse(BaseModel):
    method: str
    note: str | None
    stops: list[SuggestedStop]
    unlocated_task_ids: list[UUID]


class SaveOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_ids: list[UUID] = Field(min_length=1, max_length=200)


class NearbyItem(BaseModel):
    product_name: str
    remaining_quantity: Decimal
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    list_title: str


class NearbySupplier(BaseModel):
    supplier_id: UUID
    supplier_name: str
    contact_phone: str | None
    address: str | None
    latitude: Decimal
    longitude: Decimal
    distance_meters: int
    items: list[NearbyItem]


class NearbyResponse(BaseModel):
    radius_meters: int
    suppliers: list[NearbySupplier]
