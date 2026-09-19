"""Analytics API shapes (PHASE_08.md A/B/C/H). Every money figure carries its currency; nothing
is summed across currencies; profit always travels with its cost coverage (D-067)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PeriodInfo(BaseModel):
    key: str
    start: datetime | None
    end: datetime
    timezone: str


class CurrencyAmount(BaseModel):
    currency: str
    amount: Decimal


class ProfitByCurrency(BaseModel):
    currency: str
    gross_profit: Decimal
    covered_lines: int
    total_lines: int
    uncovered_lines: int
    coverage_percent: Decimal


class OverviewResponse(BaseModel):
    """Current state: what the current confirmed revisions and ledgers say now."""

    period: PeriodInfo
    confirmed_invoices: int
    invoiced_sales: list[CurrencyAmount]
    customer_receipts: list[CurrencyAmount]
    customer_refunds: list[CurrencyAmount]
    customer_outstanding: list[CurrencyAmount]
    customer_credit: list[CurrencyAmount]
    supplier_payable: list[CurrencyAmount]
    supplier_credit: list[CurrencyAmount]
    gross_profit: list[ProfitByCurrency]


class EventTotals(BaseModel):
    currency: str
    confirmations: Decimal
    edit_deltas: Decimal
    cancellations: Decimal
    net_effect: Decimal


class MonthlyFlow(BaseModel):
    currency: str
    month: str
    net_effect: Decimal


class EventFlowResponse(BaseModel):
    """Event flow: confirmations, accepted edit deltas and cancellation reversals dated by their
    ledger effect (PHASE_08.md B), bucketed by tenant-calendar month."""

    period: PeriodInfo
    totals: list[EventTotals]
    monthly: list[MonthlyFlow]


class InvoiceAnalytics(BaseModel):
    invoice_id: UUID
    status: str
    currency: str
    net_sales: Decimal
    discount_total: Decimal
    markup_total: Decimal
    receipts_applied: Decimal
    outstanding: Decimal
    gross_profit: ProfitByCurrency | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
