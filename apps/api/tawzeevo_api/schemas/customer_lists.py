from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from tawzeevo_api.models import InvoiceStatus
from tawzeevo_api.schemas.cash_van import CustomerResponse


class CustomerListResponse(BaseModel):
    """One page of the business's customers, by name (D-101)."""

    page: int
    limit: int
    total: int
    total_pages: int
    customers: list[CustomerResponse]


class InvoiceListRow(BaseModel):
    """An invoice as listed under its customer, with figures from its current revision."""

    id: UUID
    status: InvoiceStatus
    official_invoice_number: str | None
    confirmed_at: datetime | None
    created_at: datetime
    currency: str
    net_sales: Decimal
    total_due: Decimal
    server_revision_number: int


class InvoiceListResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    invoices: list[InvoiceListRow]
