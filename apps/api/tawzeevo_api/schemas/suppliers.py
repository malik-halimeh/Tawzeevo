from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from tawzeevo_api.models import CostSourceType, ProductPriceBasis
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone


class SupplierProfileFields(BaseModel):
    """Contact, address, saved location and notes (PHASE_06.md B). All optional."""

    model_config = ConfigDict(extra="forbid")

    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(
        default=None, ge=-180, le=180, max_digits=10, decimal_places=6
    )
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("contact_phone")
    @classmethod
    def validate_contact_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        raw_value = value.strip()
        try:
            normalize_phone(raw_value)
        except InvalidPhoneNumberError as exc:
            raise ValueError(str(exc)) from exc
        return raw_value

    @field_validator("contact_name", "address", "notes")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SupplierCreateRequest(SupplierProfileFields):
    name: str = Field(min_length=1, max_length=200)


class SupplierUpdateRequest(SupplierProfileFields):
    """Partial update; `expected_version` (when given) must match the stored row version."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    expected_version: int | None = Field(default=None, ge=1)


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    contact_name: str | None
    contact_phone: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    suppliers: list[SupplierResponse]


class ProductCostEntryCreateRequest(BaseModel):
    """Append one effective-dated, tenant-private cost entry (D-034). Entries are never edited."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID
    unit_cost: Decimal = Field(ge=0, max_digits=20, decimal_places=4)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    cost_basis: ProductPriceBasis
    pieces_per_box: int | None = Field(default=None, gt=0)
    effective_at: AwareDatetime | None = None
    # Owners may record manual costs and supplier quotes; ACTUAL_PURCHASE rows are written only by
    # the purchase finalization (P6-M4) so the history cannot claim a purchase that never happened.
    source_type: CostSourceType = CostSourceType.MANUAL
    quantity_context: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=4)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("source_type")
    @classmethod
    def owner_recordable(cls, value: CostSourceType) -> CostSourceType:
        if value not in (CostSourceType.MANUAL, CostSourceType.QUOTE):
            raise ValueError("source_type must be MANUAL or QUOTE")
        return value


class ProductCostEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_product_id: UUID
    supplier_id: UUID
    unit_cost: Decimal
    currency: str
    cost_basis: ProductPriceBasis
    pieces_per_box: int | None
    effective_at: datetime
    source_type: str
    quantity_context: Decimal | None
    notes: str | None
    created_at: datetime


class ProductCostSetupResponse(BaseModel):
    product_id: UUID
    product_name: str
    currency: str
    preferred_supplier_id: UUID | None
    entries: list[ProductCostEntryResponse]


class PreferredSupplierRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: UUID | None


class SupplierPriceInsight(BaseModel):
    """Derived, per supplier and comparable group (currency + basis + pieces per box), from the
    append-only history (PHASE_06.md C). Nothing here is stored; stale data stays visible."""

    supplier_id: UUID
    supplier_name: str
    currency: str
    cost_basis: ProductPriceBasis
    pieces_per_box: int | None
    latest_unit_cost: Decimal
    latest_effective_at: datetime
    latest_source_type: str
    latest_entry_id: UUID
    age_days: int
    lowest_unit_cost: Decimal
    highest_unit_cost: Decimal
    last_purchase_at: datetime | None
    last_purchase_unit_cost: Decimal | None
    recent_unit_costs: list[Decimal]
    entry_count: int
    variation_percent: Decimal | None
    stability: str
    is_preferred: bool


class ProductPriceInsightsResponse(BaseModel):
    product_id: UUID
    product_name: str
    currency: str
    preferred_supplier_id: UUID | None
    as_of: datetime
    stale_after_days: int
    insights: list[SupplierPriceInsight]
