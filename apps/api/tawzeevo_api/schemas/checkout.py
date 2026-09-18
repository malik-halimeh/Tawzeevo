from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tawzeevo_api.models import ProductPriceBasis
from tawzeevo_api.schemas.auth import normalize_required_text


class CheckoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal = Field(gt=0, le=Decimal("100000"), max_digits=12, decimal_places=4)
    price_basis: ProductPriceBasis = ProductPriceBasis.PIECE


class CheckoutRequest(BaseModel):
    """Mandatory contact snapshot (PHASE_05.md E); no account, no password, no age."""

    model_config = ConfigDict(extra="forbid")

    contact_name: str = Field(max_length=200)
    contact_phone: str = Field(max_length=64)
    contact_address: str = Field(max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    items: list[CheckoutItem] = Field(min_length=1, max_length=100)

    @field_validator("contact_name", "contact_phone", "contact_address", mode="before")
    @classmethod
    def validate_required(cls, value: object, info: object) -> str:
        return normalize_required_text(value, getattr(info, "field_name", "field"))


class CheckoutResponse(BaseModel):
    order_id: UUID
    status: str
    currency: str
    net_sales: Decimal
    item_count: int
    provisional_path: str
    replayed: bool = False


class ProvisionalItem(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    pieces_per_box: int | None
    unit_price: Decimal
    total: Decimal


class ProvisionalOrderResponse(BaseModel):
    """Customer-safe: no debt, history, grade, cost, driver or other-order data (PHASE_05.md F)."""

    business_name: str
    status: str
    contact_name: str
    contact_phone: str
    contact_address: str
    notes: str | None
    currency: str
    created_at: datetime
    invoice_status: str | None
    official_number: str | None
    subtotal: Decimal
    discount: Decimal
    markup: Decimal
    net_sales: Decimal
    items: list[ProvisionalItem]
    decision_note: str | None
