from __future__ import annotations

from datetime import date, datetime
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
    """Contact snapshot (PHASE_05.md E); no account, no password, no age. A public order must send
    name, phone and address (the service enforces it). A personalized order takes name and phone
    from the customer record and may leave the address blank to use the saved one (D-090)."""

    model_config = ConfigDict(extra="forbid")

    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=64)
    contact_address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    items: list[CheckoutItem] = Field(min_length=1, max_length=100)

    @field_validator("contact_name", "contact_phone", "contact_address", mode="before")
    @classmethod
    def validate_optional(cls, value: object, info: object) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
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
    delivery_date: date | None = None
    cancellation: str | None = None  # PENDING | APPROVED | REJECTED of the latest request


class CancellationRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class CancellationRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    status: str
    reason: str | None
    created_at: datetime
    decided_at: datetime | None
    decision_note: str | None


class OrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    contact_name: str
    contact_phone: str
    contact_address: str
    notes: str | None
    currency: str
    intended_customer_id: UUID | None
    intended_assurance: str | None
    linked_customer_id: UUID | None
    invoice_id: UUID | None
    delivery_date: date | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class OrderListResponse(BaseModel):
    orders: list[OrderSummary]


class CustomerCandidate(BaseModel):
    id: UUID
    name: str
    phone: str
    grade: str | None
    is_hint: bool


class OrderInvoiceLine(BaseModel):
    id: UUID
    product_name: str
    quantity: Decimal
    price_basis: ProductPriceBasis
    effective_unit_price: Decimal
    line_total: Decimal


class OrderInvoiceView(BaseModel):
    """The draft behind an order, readable before a customer is linked (the Phase 2 draft read
    requires a customer). `current_revision_id` is what a confirmation must echo back."""

    id: UUID
    status: str
    current_revision_id: UUID
    official_invoice_number: str | None
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    markup_total: Decimal
    net_sales: Decimal
    items: list[OrderInvoiceLine]


class OrderDeliveryRef(BaseModel):
    """Enough to link the order to its delivery and resume later; no driver or route data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    delivery_date: date | None


class OrderDetailResponse(BaseModel):
    order: OrderSummary
    invoice: OrderInvoiceView | None
    candidates: list[CustomerCandidate]
    cancellation_requests: list[CancellationRequestResponse]
    linked_customer_name: str | None = None
    deliveries: list[OrderDeliveryRef] = Field(default_factory=list)


class LinkCustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None
    create_from_snapshot: bool = False
    grade: str | None = Field(default=None, max_length=2)


class ConfirmOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: UUID


class DeclineOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class DeliveryDateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_date: date


class CancellationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: str | None = Field(default=None, max_length=500)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    order_id: UUID | None
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread: int
