from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tawzeevo_api.models import (
    BarcodeOwnership,
    BarcodePackageLevel,
    CustomerGrade,
    InvoiceStatus,
    MediaOwnership,
    PriceResolutionSource,
    ProductPriceBasis,
    TenantRole,
    TenantStatus,
)
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.schemas.auth import normalize_required_text


def normalize_category_slug(value: object) -> str:
    source = unicodedata.normalize("NFKC", normalize_required_text(value, "slug")).lower()
    characters: list[str] = []
    pending_separator = False
    for character in source:
        if character.isalnum():
            if pending_separator and characters:
                characters.append("-")
            characters.append(character)
            pending_separator = False
        elif character.isspace() or character in {"-", "_"}:
            pending_separator = True
    slug = "".join(characters).strip("-")
    if not slug:
        raise ValueError("slug must contain at least one letter or number")
    return slug


def normalize_barcode(value: object) -> str:
    barcode = normalize_required_text(value, "barcode")
    if any(character.isspace() for character in barcode):
        raise ValueError("barcode cannot contain whitespace")
    return barcode


class CustomerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)
    phone: str = Field(max_length=64)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(
        default=None, ge=-180, le=180, max_digits=10, decimal_places=6
    )
    grade: CustomerGrade | None = None

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

    @model_validator(mode="after")
    def validate_coordinates(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class CustomerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(
        default=None, ge=-180, le=180, max_digits=10, decimal_places=6
    )
    grade: CustomerGrade | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return normalize_required_text(value, "name")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("phone is required")
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

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one customer field is required")
        latitude_set = "latitude" in self.model_fields_set
        longitude_set = "longitude" in self.model_fields_set
        if latitude_set != longitude_set:
            raise ValueError("latitude and longitude must be updated together")
        if latitude_set and (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must both be values or both be null")
        return self


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    phone: str
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    grade: CustomerGrade | None
    created_at: datetime
    updated_at: datetime


class CustomerSearchResponse(BaseModel):
    customers: list[CustomerResponse]


class CategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    master_category_id: UUID | None = None
    name_en: str = Field(max_length=200)
    name_ar: str = Field(max_length=200)
    slug: str = Field(max_length=120)
    display_order: int = Field(default=0, ge=0)

    @field_validator("name_en", "name_ar", mode="before")
    @classmethod
    def validate_names(cls, value: object, info: object) -> str:
        return normalize_required_text(value, getattr(info, "field_name", "name"))

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, value: object) -> str:
        return normalize_category_slug(value)


class CategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_en: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    display_order: int | None = Field(default=None, ge=0)

    @field_validator("name_en", "name_ar", mode="before")
    @classmethod
    def validate_names(cls, value: object, info: object) -> str:
        return normalize_required_text(value, getattr(info, "field_name", "name"))

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, value: object) -> str:
        return normalize_category_slug(value)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one category field is required")
        return self


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    master_category_id: UUID | None
    name_en: str
    name_ar: str
    slug: str
    display_order: int
    is_active: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseModel):
    categories: list[CategoryResponse]


class TenantContextResponse(BaseModel):
    membership_id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_status: TenantStatus
    role: TenantRole


class TenantContextListResponse(BaseModel):
    tenants: list[TenantContextResponse]


class TenantProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID
    master_product_id: UUID | None = None
    name: str = Field(max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    barcode: str = Field(max_length=64)
    barcode_package_level: BarcodePackageLevel = BarcodePackageLevel.PIECE
    is_published: bool = False
    unit_price: Decimal = Field(ge=0, max_digits=20, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)
    price_basis: ProductPriceBasis
    pieces_per_box: int | None = Field(default=None, ge=1)

    @field_validator("name", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        field_name = getattr(info, "field_name", "field")
        return normalize_required_text(value, field_name)

    @field_validator("barcode", mode="before")
    @classmethod
    def validate_barcode(cls, value: object) -> str:
        return normalize_barcode(value)

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


class TenantProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: UUID | None = None
    name: str | None = Field(default=None, max_length=200)
    name_ar: str | None = Field(default=None, max_length=200)
    is_published: bool | None = None
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_basis: ProductPriceBasis | None = None
    pieces_per_box: int | None = Field(default=None, ge=1)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return normalize_required_text(value, "name")

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: object) -> str:
        currency = normalize_required_text(value, "currency").upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency must be a three-letter ISO code")
        return currency

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("at least one product field is required")
        return self


class BarcodeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    barcode: str = Field(max_length=64)
    package_level: BarcodePackageLevel = BarcodePackageLevel.PIECE

    @field_validator("barcode", mode="before")
    @classmethod
    def validate_barcode(cls, value: object) -> str:
        return normalize_barcode(value)


class BarcodeResponse(BaseModel):
    id: UUID
    barcode: str
    package_level: BarcodePackageLevel
    ownership: BarcodeOwnership


class ProductImageResponse(BaseModel):
    id: UUID
    ownership: MediaOwnership
    content_type: str
    byte_size: int
    width: int
    height: int
    display_order: int
    alt_text: str | None
    url: str


class GradeDiscountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discount_percent: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)


class GradeDiscountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    grade: CustomerGrade
    discount_percent: Decimal
    created_at: datetime
    updated_at: datetime


class GradeDiscountListResponse(BaseModel):
    discounts: list[GradeDiscountResponse]


class ProductGradePriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_price: Decimal = Field(ge=0, max_digits=20, decimal_places=4)


class ProductGradePriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    tenant_product_id: UUID
    grade: CustomerGrade
    unit_price: Decimal
    created_at: datetime
    updated_at: datetime


class ResolvedProductPriceResponse(BaseModel):
    product_id: UUID
    customer_id: UUID
    customer_grade: CustomerGrade | None
    source: PriceResolutionSource
    discount_percent: Decimal | None
    currency: str
    price_basis: ProductPriceBasis
    basis_price: Decimal
    piece_price: Decimal
    box_price: Decimal | None


class MasterProductResponse(BaseModel):
    id: UUID
    master_category_id: UUID | None
    name: str
    barcodes: list[BarcodeResponse]
    images: list[ProductImageResponse]
    created_at: datetime
    updated_at: datetime


class TenantProductResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    category_id: UUID
    master_product_id: UUID | None
    name: str
    name_ar: str | None = None
    barcode: str
    barcodes: list[BarcodeResponse]
    images: list[ProductImageResponse]
    grade_prices: list[ProductGradePriceResponse]
    is_published: bool
    unit_price: Decimal
    currency: str
    price_basis: ProductPriceBasis
    pieces_per_box: int | None
    piece_price: Decimal
    box_price: Decimal | None
    created_at: datetime
    updated_at: datetime


class TenantProductListResponse(BaseModel):
    products: list[TenantProductResponse]


class BarcodeLookupResponse(BaseModel):
    barcode: str
    ownership: BarcodeOwnership
    package_level: BarcodePackageLevel
    master_product: MasterProductResponse | None
    tenant_product: TenantProductResponse | None


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
    customer_grade: CustomerGrade | None
    price_source: PriceResolutionSource
    grade_discount_percent: Decimal | None


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
