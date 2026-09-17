from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from tawzeevo_api.models import ProductPriceBasis


class SupplierCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class SupplierUpdateRequest(SupplierCreateRequest):
    pass


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
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
    notes: str | None = Field(default=None, max_length=500)


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
