from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tawzeevo_api.models import InvoiceStatus, ProductPriceBasis
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.schemas.auth import normalize_required_text


class CustomerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)
    phone: str = Field(max_length=64)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return normalize_required_text(value, "name")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        raw_value = value.strip()
        try:
            normalize_phone(raw_value)
        except InvalidPhoneNumberError as exc:
            raise ValueError(str(exc)) from exc
        return raw_value

    @field_validator("address", mode="before")
    @classmethod
    def normalize_address(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return normalize_required_text(value, "address")


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    phone: str
    address: str | None
    created_at: datetime
    updated_at: datetime


class CustomerSearchResponse(BaseModel):
    customers: list[CustomerResponse]


class CategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return normalize_required_text(value, "name")


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseModel):
    categories: list[CategoryResponse]


class TenantProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID
    name: str = Field(max_length=200)
    barcode: str = Field(max_length=64)
    unit_price: Decimal = Field(ge=0, max_digits=20, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)
    price_basis: ProductPriceBasis
    pieces_per_box: int | None = Field(default=None, ge=1)

    @field_validator("name", "barcode", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        field_name = getattr(info, "field_name", "field")
        return normalize_required_text(value, field_name)

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: object) -> str:
        currency = normalize_required_text(value, "currency").upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency must be a three-letter ISO code")
        return currency

    @model_validator(mode="after")
    def validate_packaging(self) -> Self:
        if self.price_basis is ProductPriceBasis.BOX and self.pieces_per_box is None:
            raise ValueError("pieces_per_box is required when price_basis is BOX")
        return self


class TenantProductResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    category_id: UUID
    name: str
    barcode: str
    unit_price: Decimal
    currency: str
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    piece_price: Decimal
    box_price: Decimal | None
    created_at: datetime
    updated_at: datetime


class DraftInvoiceItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)


class DraftInvoiceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    items: list[DraftInvoiceItemCreateRequest] = Field(min_length=1, max_length=200)


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str
    barcode: str
    quantity: Decimal
    price_basis: ProductPriceBasis
    unit_price: Decimal
    line_total: Decimal


class DraftInvoiceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer: CustomerResponse
    status: InvoiceStatus
    currency: str
    subtotal: Decimal
    items: list[InvoiceItemResponse]
    created_at: datetime
    updated_at: datetime
