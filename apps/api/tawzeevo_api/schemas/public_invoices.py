from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from tawzeevo_api.models import InvoiceStatus, ProductPriceBasis


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class IssuedCapabilityResponse(CapabilityResponse):
    # Returned once. Neither raw tokens nor URLs are persisted or audited.
    public_path: str
    customer_phone: str | None
    summary: str


class PublicInvoiceItem(BaseModel):
    name: str
    barcode: str | None
    quantity: Decimal
    unit: ProductPriceBasis
    pieces_per_box: int | None
    unit_price: Decimal
    discount: Decimal
    markup: Decimal
    total: Decimal


class PublicInvoiceResponse(BaseModel):
    business_name: str
    customer_name: str | None
    status: InvoiceStatus
    number: str | None
    revision: int
    currency: str
    subtotal: Decimal
    discount: Decimal
    markup: Decimal
    net_sales: Decimal
    items: list[PublicInvoiceItem]
