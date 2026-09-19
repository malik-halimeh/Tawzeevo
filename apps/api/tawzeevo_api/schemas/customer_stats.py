"""Customer lifetime statistics shapes (PHASE_08.md D; D-069)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CurrencyStat(BaseModel):
    currency: str
    total_purchased: Decimal
    invoice_count: int
    largest_invoice: Decimal | None
    average_invoice: Decimal | None
    total_receipts: Decimal
    total_refunds: Decimal
    outstanding: Decimal
    credit: Decimal
    total_discounts: Decimal
    total_markups: Decimal


class TopItem(BaseModel):
    currency: str
    name: str
    product_id: UUID | None
    quantity: Decimal
    value: Decimal


class MonthlySpend(BaseModel):
    currency: str
    month: str
    amount: Decimal


class GradePoint(BaseModel):
    at: datetime
    grade: str | None


class CustomerLifetimeResponse(BaseModel):
    customer_id: UUID
    customer_name: str
    current_grade: str | None
    as_of: datetime
    financial: list[CurrencyStat]
    invoice_count: int
    cancelled_invoices: int
    cancellation_requests: int
    first_purchase_at: datetime | None
    latest_purchase_at: datetime | None
    average_days_between_purchases: Decimal | None
    purchases_per_month: Decimal | None
    late_payment_count: int
    overdue_threshold_days: int | None
    monthly_spend: list[MonthlySpend]
    top_products: list[TopItem]
    top_categories: list[TopItem]
    grade_timeline: list[GradePoint]
    insufficient_data: bool
