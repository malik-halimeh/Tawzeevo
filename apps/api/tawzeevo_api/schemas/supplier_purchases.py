"""Supplier purchase API shapes (PHASE_06.md G/H; D-038, D-039)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from tawzeevo_api.models import ProductPriceBasis


class PurchaseLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    unit_cost: Decimal = Field(ge=0, max_digits=20, decimal_places=4)
    price_basis: ProductPriceBasis | None = None
    pieces_per_box: int | None = Field(default=None, gt=0)
    procurement_item_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=500)


class PurchaseCreateRequest(BaseModel):
    """One immutable purchase; `idempotency_key` makes a retry return the same purchase."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    supplier_id: UUID
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    purchased_at: AwareDatetime | None = None
    procurement_list_id: UUID | None = None
    supplier_reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    items: list[PurchaseLineRequest] = Field(min_length=1, max_length=200)


class PurchaseReverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    reason: str = Field(min_length=1, max_length=500)


class PurchaseLineResponse(BaseModel):
    id: UUID
    line_number: int
    product_id: UUID
    product_name: str
    procurement_item_id: UUID | None
    quantity: Decimal
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    unit_cost: Decimal
    line_total: Decimal
    cost_entry_id: UUID | None
    notes: str | None


class PurchaseResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    procurement_list_id: UUID | None
    purchased_at: datetime
    currency: str
    total_amount: Decimal
    supplier_reference: str | None
    notes: str | None
    created_at: datetime
    reversed_at: datetime | None
    reversal_reason: str | None
    replayed: bool
    items: list[PurchaseLineResponse]


class PurchaseListResponse(BaseModel):
    purchases: list[PurchaseResponse]


class CurrencyTotal(BaseModel):
    currency: str
    outstanding: Decimal
    credit: Decimal
    parties: int


class OutstandingTotalsResponse(BaseModel):
    """Customer outstanding and supplier payable by currency (D-066): positive balances summed,
    credits shown separately, never netted, never summed across currencies."""

    customers: list[CurrencyTotal]
    suppliers: list[CurrencyTotal]
