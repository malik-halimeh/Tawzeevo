"""OE-06b business-wide projections; the customer-scoped contract stays unchanged."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from tawzeevo_api.models import InvoiceStatus
from tawzeevo_api.schemas.customer_lists import InvoiceListRow

type PaidState = Literal["UNPAID", "PARTLY_PAID", "PAID"]


class InvoiceListFilters(BaseModel):
    status: InvoiceStatus | None = None
    paid_state: Literal["UNPAID", "PARTLY_PAID", "PAID", "OPEN"] | None = None
    overdue: bool | None = None
    customer_id: UUID | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = Field(default=None, max_length=200)


class BusinessInvoiceListQuery(InvoiceListFilters):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class BusinessInvoiceListRow(InvoiceListRow):
    # Customer-less drafts are legal and must also appear in the business-wide list.
    customer_id: UUID | None
    customer_name: str | None
    outstanding: Decimal
    paid_state: PaidState | None
    is_overdue: bool
    overdue_age_days: int | None


class BusinessInvoiceListResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    invoices: list[BusinessInvoiceListRow]


class InvoiceCurrencySummary(BaseModel):
    currency: str
    outstanding_total: Decimal
    overdue_total: Decimal
    open_count: int
    overdue_count: int
    paid_count: int
    draft_count: int


class InvoiceSummaryResponse(BaseModel):
    currencies: list[InvoiceCurrencySummary]
