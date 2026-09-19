"""Procurement API shapes (PHASE_06.md E/F/J; D-058). Quantities are demand and purchasing
progress only. The driver projection deliberately has no price, cost or estimate fields."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from tawzeevo_api.models import ProductPriceBasis

Quantity = Field(ge=0, max_digits=20, decimal_places=4)


class GenerateListRequest(BaseModel):
    """Build a list from confirmed demand in a date range (tenant calendar, inclusive)."""

    model_config = ConfigDict(extra="forbid")

    demand_from: date
    demand_to: date
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    include_empty: bool = False


class ManualItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    target_quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    price_basis: ProductPriceBasis | None = None
    supplier_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=500)


class ItemUpdateRequest(BaseModel):
    """Partial edit with the row version; `target_quantity` never touches `required_quantity`."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    target_quantity: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    supplier_id: UUID | None = None
    clear_supplier: bool = False
    notes: str | None = Field(default=None, max_length=500)


class ItemRemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=300)


class ItemWaiveRequest(ItemRemoveRequest):
    pass


class AssigneeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    membership_id: UUID | None


class ListCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class CarryForwardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    complete_source: bool = True


class Estimate(BaseModel):
    """Clearly labelled estimate from the latest comparable price of the chosen (or recommended)
    supplier; absent when nothing comparable exists."""

    supplier_id: UUID
    supplier_name: str
    unit_cost: Decimal
    currency: str
    effective_at: datetime
    age_days: int
    is_stale: bool
    source_type: str
    remaining_cost: Decimal
    supplier_is_recommended: bool


class ProcurementItemResponse(BaseModel):
    id: UUID
    list_id: UUID
    product_id: UUID
    product_name: str
    supplier_id: UUID | None
    supplier_name: str | None
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    origin: str
    required_quantity: Decimal
    target_quantity: Decimal
    purchased_quantity: Decimal
    remaining_quantity: Decimal
    demand_invoice_count: int
    removed_at: datetime | None
    remove_reason: str | None
    waived_at: datetime | None
    waive_reason: str | None
    carried_from_item_id: UUID | None
    carried_to_item_id: UUID | None
    notes: str | None
    version: int
    estimate: Estimate | None


class AssigneeResponse(BaseModel):
    membership_id: UUID
    role: str
    display_name: str
    is_self: bool


class ProcurementListResponse(BaseModel):
    id: UUID
    status: str
    title: str
    demand_from: date | None
    demand_to: date | None
    notes: str | None
    assignee: AssigneeResponse | None
    carried_from_list_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    items: list[ProcurementItemResponse]
    estimated_totals: dict[str, Decimal]
    open_line_count: int


class ProcurementListSummary(BaseModel):
    id: UUID
    status: str
    title: str
    demand_from: date | None
    demand_to: date | None
    assignee: AssigneeResponse | None
    created_at: datetime
    line_count: int
    open_line_count: int


class ProcurementListPage(BaseModel):
    lists: list[ProcurementListSummary]


class AssigneeListResponse(BaseModel):
    assignees: list[AssigneeResponse]


# --- Driver / runner projection: operational pickup only (PHASE_06.md F) -----------------------


class PickupItem(BaseModel):
    item_id: UUID
    product_name: str
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    remaining_quantity: Decimal
    notes: str | None


class PickupSupplier(BaseModel):
    supplier_id: UUID | None
    supplier_name: str | None
    contact_name: str | None
    contact_phone: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    items: list[PickupItem]


class PickupList(BaseModel):
    list_id: UUID
    title: str
    status: str
    notes: str | None
    suppliers: list[PickupSupplier]


class PickupResponse(BaseModel):
    lists: list[PickupList]
