from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tawzeevo_api.models import (
    CustomerGrade,
    InvoiceStatus,
    PriceResolutionSource,
    ProductPriceBasis,
)


class CalculatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=120)


class CalculatorResponse(BaseModel):
    expression: str
    value: Decimal


class AcceptedFuzzyMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)
    selected_product_id: UUID
    score: Decimal = Field(ge=0, le=1, max_digits=5, decimal_places=4)


class InvoiceEditorItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID | None = None
    manual_name: str | None = Field(default=None, min_length=1, max_length=200)
    barcode: str | None = Field(default=None, max_length=64)
    quantity_expression: str = Field(min_length=1, max_length=120)
    price_basis: ProductPriceBasis = ProductPriceBasis.PIECE
    pieces_per_box: int | None = Field(default=None, gt=0)
    manual_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    line_discount_expression: str = Field(default="0", min_length=1, max_length=120)
    line_markup_expression: str = Field(default="0", min_length=1, max_length=120)
    supplier_id: UUID | None = None
    cost_override: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    cost_basis: ProductPriceBasis | None = None
    cost_pieces_per_box: int | None = Field(default=None, gt=0)
    cost_override_reason: str | None = Field(default=None, max_length=500)
    accepted_fuzzy_match: AcceptedFuzzyMatch | None = None

    @model_validator(mode="after")
    def validate_identity_and_override(self) -> InvoiceEditorItemRequest:
        if (self.product_id is None) == (self.manual_name is None):
            raise ValueError("Provide exactly one of product_id or manual_name")
        if self.product_id is not None and self.manual_unit_price is not None:
            raise ValueError("Catalog product prices are resolved by the backend")
        if self.product_id is None and self.manual_unit_price is None:
            raise ValueError("manual_unit_price is required for a manual item")
        if (
            self.product_id is None
            and self.price_basis is ProductPriceBasis.BOX
            and self.pieces_per_box is None
        ):
            raise ValueError("pieces_per_box is required for a BOX manual item")
        if self.cost_override is None:
            if self.cost_override_reason is not None:
                raise ValueError("cost_override_reason requires cost_override")
        elif not self.cost_override_reason or not self.cost_override_reason.strip():
            raise ValueError("cost_override_reason is required for a cost override")
        if (
            self.accepted_fuzzy_match is not None
            and self.product_id != self.accepted_fuzzy_match.selected_product_id
        ):
            raise ValueError("Accepted fuzzy selection must match product_id")
        return self


class InvoiceEditorDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_command_id: UUID
    expected_predecessor_revision_id: UUID | None = None
    customer_id: UUID
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    invoice_discount_expression: str = Field(default="0", min_length=1, max_length=120)
    invoice_markup_expression: str = Field(default="0", min_length=1, max_length=120)
    reason: str | None = Field(default=None, max_length=500)
    items: list[InvoiceEditorItemRequest] = Field(min_length=1, max_length=200)


class InvoiceEditorItemResponse(BaseModel):
    id: UUID
    line_number: int
    product_id: UUID | None
    product_name: str
    barcode: str | None
    media_snapshot: dict[str, object]
    quantity: Decimal
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    normal_unit_price: Decimal
    effective_unit_price: Decimal
    customer_grade: CustomerGrade | None
    price_source: PriceResolutionSource
    grade_discount_percent: Decimal | None
    line_discount: Decimal
    line_markup: Decimal
    line_total: Decimal
    supplier_id: UUID | None
    product_cost_entry_id: UUID | None
    unit_cost: Decimal | None
    cost_currency: str | None
    cost_basis: ProductPriceBasis | None
    cost_pieces_per_box: int | None
    cost_source_type: str | None
    is_cost_override: bool
    cost_override_reason: str | None


class InvoiceEditorResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    status: InvoiceStatus
    official_invoice_number: str | None
    confirmed_at: datetime | None
    customer_id: UUID
    customer_snapshot: dict[str, object]
    current_revision_id: UUID
    server_revision_number: int
    pricing_version: Literal["pricing-v1"]
    currency: str
    prior_balance: Decimal
    subtotal: Decimal
    discount_total: Decimal
    markup_total: Decimal
    net_sales: Decimal
    total_due: Decimal
    items: list[InvoiceEditorItemResponse]
    created_at: datetime
    updated_at: datetime


class InvoiceConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: UUID


class InvoiceCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    reason: str | None = Field(default=None, max_length=500)


class InvoiceHistoryRevisionResponse(InvoiceEditorResponse):
    predecessor_revision_id: UUID | None
    reason: str | None
    revision_created_at: datetime
    is_current: bool
    ledger_delta: Decimal | None


class InvoiceHistoryResponse(BaseModel):
    revisions: list[InvoiceHistoryRevisionResponse]


class CatalogMatchResponse(BaseModel):
    product_id: UUID
    name: str
    barcode: str
    package_level: ProductPriceBasis
    currency: str
    price_basis: ProductPriceBasis
    unit_price: Decimal
    image_url: str | None
    match_type: Literal["EXACT", "PREFIX", "FUZZY"]
    score: Decimal


class CatalogSearchResponse(BaseModel):
    matches: list[CatalogMatchResponse]


class ProductCostOptionResponse(BaseModel):
    supplier_id: UUID
    supplier_name: str
    is_preferred: bool
    product_cost_entry_id: UUID | None
    unit_cost: Decimal | None
    currency: str
    cost_basis: ProductPriceBasis
    pieces_per_box: int | None
    effective_at: datetime | None


class ProductCostOptionsResponse(BaseModel):
    options: list[ProductCostOptionResponse]


class ParsedItemResponse(BaseModel):
    source_text: str
    normalized_query: str
    quantity: Decimal
    resolution: Literal["EXACT", "AMBIGUOUS", "UNRESOLVED"]
    selected: CatalogMatchResponse | None
    suggestions: list[CatalogMatchResponse]


class ItemParserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=5000)


class ItemParserResponse(BaseModel):
    threshold: Decimal
    items: list[ParsedItemResponse]
