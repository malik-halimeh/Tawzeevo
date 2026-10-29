from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from tawzeevo_api.models import InvoiceStatus
from tawzeevo_api.schemas.cash_van import CustomerResponse
from tawzeevo_api.schemas.customer_ledger import CustomerBalanceResponse

CustomerListSort = Literal["name", "newest", "owes_most"]


class CustomerListRow(CustomerResponse):
    balances: list[CustomerBalanceResponse] = Field(default_factory=list)


class CustomerListResponse(BaseModel):
    """One filtered, sorted page of the business's customers (D-101, OE-03b)."""

    page: int
    limit: int
    total: int
    total_pages: int
    customers: list[CustomerListRow]


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
