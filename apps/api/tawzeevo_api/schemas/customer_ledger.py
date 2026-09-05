from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tawzeevo_api.models import LedgerEntryType


class OpeningBalanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    customer_id: UUID
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    signed_amount: Decimal = Field(max_digits=20, decimal_places=4)
    effective_at: datetime
    note: str | None = Field(default=None, max_length=500)

    @field_validator("signed_amount")
    @classmethod
    def amount_must_be_nonzero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Opening balance cannot be zero")
        return value


class CustomerLedgerEntryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    currency: str
    signed_amount: Decimal
    entry_type: LedgerEntryType
    effective_at: datetime
    created_at: datetime


class CustomerBalanceResponse(BaseModel):
    currency: str
    balance: Decimal


class CustomerBalancesResponse(BaseModel):
    customer_id: UUID
    customer_name: str
    balances: list[CustomerBalanceResponse]


class FinancialSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_overdue_threshold_days: int | None = Field(default=None, ge=0)


class FinancialSettingsResponse(BaseModel):
    tenant_id: UUID
    customer_overdue_threshold_days: int | None


class CustomerDebtResponse(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_phone: str
    currency: str
    balance: Decimal
    oldest_unpaid_at: datetime | None
    overdue_age_days: int | None
    overdue_threshold_days: int | None
    is_overdue: bool
    alert_key: str | None


class CustomerDebtListResponse(BaseModel):
    debts: list[CustomerDebtResponse]
