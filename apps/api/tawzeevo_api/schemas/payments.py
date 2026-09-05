from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tawzeevo_api.models import AllocationKind, PaymentDirection


class AllocationSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ledger_entry_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=4)


class CustomerReceiptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    customer_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    method: str | None = Field(default=None, max_length=80)
    reference: str | None = Field(default=None, max_length=200)
    paid_at: datetime
    notes: str | None = Field(default=None, max_length=500)
    allocations: list[AllocationSelectionRequest] | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def allocation_targets_are_unique(self) -> CustomerReceiptRequest:
        if self.allocations is not None:
            targets = [allocation.target_ledger_entry_id for allocation in self.allocations]
            if len(targets) != len(set(targets)):
                raise ValueError("Each explicit allocation target may appear only once")
        return self


class PaymentReversalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    reason: str = Field(min_length=1, max_length=500)


class CustomerRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    customer_id: UUID
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    method: str | None = Field(default=None, max_length=80)
    reference: str | None = Field(default=None, max_length=200)
    paid_at: datetime
    notes: str | None = Field(default=None, max_length=500)


class PaymentAllocationResponse(BaseModel):
    id: UUID
    target_ledger_entry_id: UUID
    amount: Decimal
    kind: AllocationKind
    reverses_allocation_id: UUID | None
    effective_amount: Decimal
    created_at: datetime


class CustomerPaymentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    direction: PaymentDirection
    amount: Decimal
    currency: str
    method: str | None
    reference: str | None
    paid_at: datetime
    recorded_at: datetime
    reverses_payment_id: UUID | None
    notes: str | None
    allocated_amount: Decimal
    unallocated_amount: Decimal
    customer_balance: Decimal
    available_credit: Decimal
    allocations: list[PaymentAllocationResponse]


class CustomerObligationResponse(BaseModel):
    target_ledger_entry_id: UUID
    source_type: str
    source_id: UUID | None
    label: str
    effective_at: datetime
    original_amount: Decimal
    allocated_amount: Decimal
    outstanding_amount: Decimal


class CustomerObligationListResponse(BaseModel):
    customer_id: UUID
    currency: str
    obligations: list[CustomerObligationResponse]
