from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, field_validator

from tawzeevo_api.models import PaymentDirection


class SupplierPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    supplier_id: UUID
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    paid_at: AwareDatetime
    method: str | None = Field(default=None, max_length=80)
    reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)


class SupplierOpeningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    supplier_id: UUID
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    signed_amount: Decimal = Field(max_digits=20, decimal_places=4)
    effective_at: AwareDatetime
    note: str | None = Field(default=None, max_length=500)

    @field_validator("signed_amount")
    @classmethod
    def nonzero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Opening balance must be nonzero")
        return value


class SupplierCurrencyBalance(BaseModel):
    currency: str
    balance: Decimal


class SupplierBalancesResponse(BaseModel):
    supplier_id: UUID
    balances: list[SupplierCurrencyBalance]


class SupplierPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supplier_id: UUID
    direction: PaymentDirection
    currency: str
    amount: Decimal
    paid_at: datetime
    method: str | None
    reference: str | None
    notes: str | None
    reverses_payment_id: UUID | None

    @field_serializer("paid_at")
    def serialize_paid_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat()
