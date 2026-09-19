from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawzeevo_api.database import Base


class SystemUserType(StrEnum):
    ADMIN = "admin"
    CLIENT = "client"


class TenantStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class TenantRole(StrEnum):
    OWNER = "owner"
    DRIVER = "driver"


class TenantApplicationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SuspensionReason(StrEnum):
    SUBSCRIPTION_OVERDUE = "SUBSCRIPTION_OVERDUE"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    SECURITY = "SECURITY"
    OTHER = "OTHER"


class ProductPriceBasis(StrEnum):
    PIECE = "PIECE"
    BOX = "BOX"


class BarcodePackageLevel(StrEnum):
    PIECE = "PIECE"
    BOX = "BOX"


class BarcodeOwnership(StrEnum):
    MASTER = "MASTER"
    TENANT = "TENANT"


class MediaOwnership(StrEnum):
    MASTER = "MASTER"
    TENANT = "TENANT"


class CustomerGrade(StrEnum):
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"


class PriceResolutionSource(StrEnum):
    NORMAL = "NORMAL"
    GRADE_DISCOUNT = "GRADE_DISCOUNT"
    EXPLICIT_GRADE_PRICE = "EXPLICIT_GRADE_PRICE"


class InvoiceStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class LedgerEntryType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"
    OPENING_BALANCE_CORRECTION = "OPENING_BALANCE_CORRECTION"
    INVOICE_CHARGE = "INVOICE_CHARGE"
    INVOICE_ADJUSTMENT = "INVOICE_ADJUSTMENT"
    INVOICE_REVERSAL = "INVOICE_REVERSAL"
    CUSTOMER_PAYMENT = "CUSTOMER_PAYMENT"
    CUSTOMER_PAYMENT_REVERSAL = "CUSTOMER_PAYMENT_REVERSAL"
    CUSTOMER_REFUND = "CUSTOMER_REFUND"
    AUTHORIZED_MANUAL_ADJUSTMENT = "AUTHORIZED_MANUAL_ADJUSTMENT"


class PaymentDirection(StrEnum):
    CUSTOMER_RECEIPT = "CUSTOMER_RECEIPT"
    CUSTOMER_RECEIPT_REVERSAL = "CUSTOMER_RECEIPT_REVERSAL"
    CUSTOMER_REFUND = "CUSTOMER_REFUND"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"
    SUPPLIER_PAYMENT_REVERSAL = "SUPPLIER_PAYMENT_REVERSAL"


class AllocationKind(StrEnum):
    APPLY = "APPLY"
    REVERSAL = "REVERSAL"


class SupplierLedgerEntryType(StrEnum):
    OPENING_BALANCE = "OPENING_BALANCE"
    OPENING_BALANCE_CORRECTION = "OPENING_BALANCE_CORRECTION"
    PURCHASE_CHARGE = "PURCHASE_CHARGE"
    PURCHASE_ADJUSTMENT = "PURCHASE_ADJUSTMENT"
    SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT"
    SUPPLIER_PREPAYMENT = "SUPPLIER_PREPAYMENT"
    SUPPLIER_PAYMENT_REVERSAL = "SUPPLIER_PAYMENT_REVERSAL"
    PURCHASE_REVERSAL = "PURCHASE_REVERSAL"
    AUTHORIZED_MANUAL_ADJUSTMENT = "AUTHORIZED_MANUAL_ADJUSTMENT"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [str(member.value) for member in enum_class]


user_type_enum = ENUM(SystemUserType, name="system_user_type", values_callable=enum_values)
tenant_status_enum = ENUM(TenantStatus, name="tenant_status", values_callable=enum_values)
tenant_role_enum = ENUM(TenantRole, name="tenant_role", values_callable=enum_values)
tenant_application_status_enum = ENUM(
    TenantApplicationStatus, name="tenant_application_status", values_callable=enum_values
)
suspension_reason_enum = ENUM(
    SuspensionReason, name="suspension_reason", values_callable=enum_values
)
product_price_basis_enum = ENUM(
    ProductPriceBasis, name="product_price_basis", values_callable=enum_values
)
barcode_package_level_enum = ENUM(
    BarcodePackageLevel, name="barcode_package_level", values_callable=enum_values
)
customer_grade_enum = ENUM(CustomerGrade, name="customer_grade", values_callable=enum_values)
price_resolution_source_enum = ENUM(
    PriceResolutionSource, name="price_resolution_source", values_callable=enum_values
)
invoice_status_enum = ENUM(InvoiceStatus, name="invoice_status", values_callable=enum_values)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    phone_raw: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[SystemUserType] = mapped_column(user_type_enum, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    security_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint("age BETWEEN 1 AND 120", name="ck_users_age_range"),
        Index("ix_users_email_unique", "email", unique=True),
    )


class AuthSession(TimestampMixin, Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    security_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(80))
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="SET NULL")
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # Public storefront address (D-047): routing identity only, never authorization. The default
    # is a random placeholder; approval assigns a name-derived slug through services.storefront.
    slug: Mapped[str] = mapped_column(
        String(50), nullable=False, default=lambda: f"shop-{uuid4().hex[:10]}"
    )
    # D-072: business default customer access policy; Phase 5 enforces LINK only.
    customer_access_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="LINK", server_default="LINK"
    )
    status: Mapped[TenantStatus] = mapped_column(
        tenant_status_enum, default=TenantStatus.ACTIVE, server_default="ACTIVE", nullable=False
    )
    access_until: Mapped[date | None] = mapped_column(Date)
    grace_until: Mapped[date | None] = mapped_column(Date)
    suspension_reason: Mapped[SuspensionReason | None] = mapped_column(suspension_reason_enum)
    sync_retention_floor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"), default=0
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "grace_until IS NULL OR access_until IS NULL OR grace_until >= access_until",
            name="ck_tenants_grace_not_before_access",
        ),
        CheckConstraint(
            "slug ~ '^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$'", name="ck_tenants_slug_format"
        ),
        CheckConstraint(
            "customer_access_policy IN ('LINK', 'VERIFIED', 'ACCOUNT_REQUIRED')",
            name="ck_tenants_customer_access_policy",
        ),
        Index("uq_tenants_slug", "slug", unique=True),
    )


class TenantSlugRedirect(Base):
    """A previous storefront slug that still resolves to its business (D-047, audited rename)."""

    __tablename__ = "tenant_slug_redirects"

    slug: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    renamed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TenantFinancialSettings(TimestampMixin, Base):
    __tablename__ = "tenant_financial_settings"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    customer_overdue_threshold_days: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "customer_overdue_threshold_days IS NULL OR customer_overdue_threshold_days >= 0",
            name="ck_tenant_financial_settings_overdue_nonnegative",
        ),
    )


class TenantMembership(TimestampMixin, Base):
    __tablename__ = "tenant_memberships"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[TenantRole] = mapped_column(tenant_role_enum, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_tenant_memberships_tenant_user_unique", "tenant_id", "user_id", unique=True),
    )


class TenantInvitation(TimestampMixin, Base):
    __tablename__ = "tenant_invitations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[TenantRole] = mapped_column(tenant_role_enum, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantApplication(TimestampMixin, Base):
    __tablename__ = "tenant_applications"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    applicant_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[TenantApplicationStatus] = mapped_column(
        tenant_application_status_enum,
        default=TenantApplicationStatus.PENDING,
        server_default="PENDING",
        nullable=False,
        index=True,
    )
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), unique=True
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    phone_raw: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    grade: Mapped[CustomerGrade | None] = mapped_column(customer_grade_enum)
    # D-072: optional per-customer access policy override (LINK | VERIFIED | ACCOUNT_REQUIRED).
    access_policy_override: Mapped[str | None] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )

    __table_args__ = (
        CheckConstraint(
            "access_policy_override IS NULL OR access_policy_override IN "
            "('LINK', 'VERIFIED', 'ACCOUNT_REQUIRED')",
            name="ck_customers_access_policy_override",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_customers_id_tenant"),
        Index("ix_customers_tenant_phone", "tenant_id", "phone"),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_customers_coordinates_paired",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_customers_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_customers_longitude_range",
        ),
    )


class MasterCategory(TimestampMixin, Base):
    __tablename__ = "master_categories"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "(is_active AND archived_at IS NULL) OR (NOT is_active AND archived_at IS NOT NULL)",
            name="ck_master_categories_archive_state",
        ),
    )


class MasterCatalogImport(TimestampMixin, Base):
    __tablename__ = "master_catalog_imports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_license: Mapped[str] = mapped_column(String(100), nullable=False)
    source_license_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_attribution: Mapped[str] = mapped_column(String(300), nullable=False)
    import_version: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reused_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint("length(dataset_sha256) = 64", name="ck_catalog_imports_sha256_length"),
        CheckConstraint(
            "record_count >= 0 AND inserted_count >= 0 AND reused_count >= 0 "
            "AND rejected_count >= 0 AND duplicate_count >= 0",
            name="ck_catalog_imports_counts_nonnegative",
        ),
    )


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    master_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("master_categories.id", ondelete="RESTRICT"), index=True
    )
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_categories_id_tenant"),
        UniqueConstraint("tenant_id", "slug", name="uq_categories_tenant_slug"),
        CheckConstraint("display_order >= 0", name="ck_categories_display_order_nonnegative"),
        CheckConstraint(
            "(is_active AND archived_at IS NULL) OR (NOT is_active AND archived_at IS NOT NULL)",
            name="ck_categories_archive_state",
        ),
        Index("ix_categories_tenant_active_order", "tenant_id", "is_active", "display_order"),
    )


class MasterProduct(TimestampMixin, Base):
    __tablename__ = "master_products"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    master_category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("master_categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class MasterProductSource(TimestampMixin, Base):
    __tablename__ = "master_product_sources"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    master_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("master_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    catalog_import_id: Mapped[UUID] = mapped_column(
        ForeignKey("master_catalog_imports.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_product_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_categories: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(100), nullable=False)
    source_last_modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "catalog_import_id",
            "source_product_id",
            name="uq_master_product_sources_import_product",
        ),
        Index(
            "ix_master_product_sources_product_import",
            "master_product_id",
            "catalog_import_id",
        ),
    )


class MasterBarcode(TimestampMixin, Base):
    __tablename__ = "master_barcodes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    master_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("master_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    barcode: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    package_level: Mapped[BarcodePackageLevel] = mapped_column(
        barcode_package_level_enum, nullable=False
    )


class MasterProductImage(TimestampMixin, Base):
    __tablename__ = "master_product_images"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    master_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("master_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    alt_text: Mapped[str | None] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_master_product_images_byte_size_positive"),
        CheckConstraint(
            "width > 0 AND height > 0", name="ck_master_product_images_dimensions_positive"
        ),
        CheckConstraint(
            "display_order >= 0", name="ck_master_product_images_display_order_nonnegative"
        ),
        Index(
            "ix_master_product_images_product_order",
            "master_product_id",
            "display_order",
            "id",
        ),
    )


class TenantProduct(TimestampMixin, Base):
    __tablename__ = "tenant_products"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    master_product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("master_products.id", ondelete="RESTRICT"), index=True
    )
    preferred_supplier_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(200))
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    pieces_per_box: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "tenant_id"],
            ["categories.id", "categories.tenant_id"],
            ondelete="RESTRICT",
            name="fk_tenant_products_category_tenant",
        ),
        ForeignKeyConstraint(
            ["preferred_supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_tenant_products_preferred_supplier_tenant",
            use_alter=True,
        ),
        UniqueConstraint("id", "tenant_id", name="uq_tenant_products_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "master_product_id",
            name="uq_tenant_products_tenant_master_product",
        ),
        Index(
            "ix_tenant_products_tenant_published",
            "tenant_id",
            "is_published",
        ),
        CheckConstraint("unit_price >= 0", name="ck_tenant_products_unit_price_nonnegative"),
        CheckConstraint(
            "pieces_per_box IS NULL OR pieces_per_box > 0",
            name="ck_tenant_products_pieces_per_box_positive",
        ),
        CheckConstraint(
            "price_basis != 'BOX' OR pieces_per_box IS NOT NULL",
            name="ck_tenant_products_box_basis_has_piece_count",
        ),
    )


class TenantBarcode(TimestampMixin, Base):
    __tablename__ = "tenant_barcodes"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    barcode: Mapped[str] = mapped_column(String(64), nullable=False)
    package_level: Mapped[BarcodePackageLevel] = mapped_column(
        barcode_package_level_enum, nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="CASCADE",
            name="fk_tenant_barcodes_product_tenant",
        ),
        Index(
            "ix_tenant_barcodes_tenant_barcode_unique",
            "tenant_id",
            "barcode",
            unique=True,
        ),
        Index(
            "ix_tenant_barcodes_product_tenant",
            "tenant_product_id",
            "tenant_id",
        ),
    )


class TenantGradeDiscount(TimestampMixin, Base):
    __tablename__ = "tenant_grade_discounts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade: Mapped[CustomerGrade] = mapped_column(customer_grade_enum, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "grade", name="uq_tenant_grade_discounts_tenant_grade"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_tenant_grade_discounts_percent_range",
        ),
    )


class ProductGradePrice(TimestampMixin, Base):
    __tablename__ = "product_grade_prices"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    grade: Mapped[CustomerGrade] = mapped_column(customer_grade_enum, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="CASCADE",
            name="fk_product_grade_prices_product_tenant",
        ),
        UniqueConstraint(
            "tenant_id",
            "tenant_product_id",
            "grade",
            name="uq_product_grade_prices_product_grade",
        ),
        CheckConstraint("unit_price >= 0", name="ck_product_grade_prices_unit_price_nonnegative"),
        Index(
            "ix_product_grade_prices_product_tenant",
            "tenant_product_id",
            "tenant_id",
        ),
    )


class TenantProductImage(TimestampMixin, Base):
    __tablename__ = "tenant_product_images"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    alt_text: Mapped[str | None] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="CASCADE",
            name="fk_tenant_product_images_product_tenant",
        ),
        CheckConstraint("byte_size > 0", name="ck_tenant_product_images_byte_size_positive"),
        CheckConstraint(
            "width > 0 AND height > 0", name="ck_tenant_product_images_dimensions_positive"
        ),
        CheckConstraint(
            "display_order >= 0", name="ck_tenant_product_images_display_order_nonnegative"
        ),
        Index(
            "ix_tenant_product_images_product_tenant_order",
            "tenant_product_id",
            "tenant_id",
            "display_order",
            "id",
        ),
    )


class CostSourceType(StrEnum):
    """Provenance of a cost entry (D-034, D-059). Invoice entry prefers ACTUAL_PURCHASE, then
    QUOTE, then the manual kinds; historical invoice snapshots are never rewritten."""

    MANUAL = "MANUAL"
    OWNER_OVERRIDE = "OWNER_OVERRIDE"
    QUOTE = "QUOTE"
    ACTUAL_PURCHASE = "ACTUAL_PURCHASE"


class TenantSupplier(TimestampMixin, Base):
    """Tenant-private supplier profile (PHASE_06.md B): identity, contact, address, saved location,
    notes. `version` lets offline edits carry an expected version (Phase 4 sync semantics)."""

    __tablename__ = "tenant_suppliers"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_phone_raw: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    notes: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_tenant_suppliers_id_tenant"),
        Index("ix_tenant_suppliers_tenant_name", "tenant_id", "name"),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_tenant_suppliers_coordinates_paired",
        ),
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_tenant_suppliers_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_tenant_suppliers_longitude_range",
        ),
    )


class TenantProductCostEntry(Base):
    __tablename__ = "tenant_product_cost_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    cost_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    pieces_per_box: Mapped[int | None] = mapped_column(Integer)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    # Quantity the price was quoted or bought for (PHASE_06.md C "quantity context"); optional.
    quantity_context: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_product_cost_entries_product_tenant",
        ),
        ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_product_cost_entries_supplier_tenant",
        ),
        CheckConstraint(
            "source_type IN ('MANUAL', 'OWNER_OVERRIDE', 'QUOTE', 'ACTUAL_PURCHASE')",
            name="ck_tenant_product_cost_entries_source_type",
        ),
        CheckConstraint(
            "quantity_context IS NULL OR quantity_context > 0",
            name="ck_tenant_product_cost_entries_quantity_context_positive",
        ),
        Index(
            "ix_tenant_product_cost_entries_product_supplier_effective",
            "tenant_id",
            "tenant_product_id",
            "supplier_id",
            "effective_at",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            "tenant_product_id",
            "supplier_id",
            name="uq_product_cost_entries_identity_scope",
        ),
        CheckConstraint("unit_cost >= 0", name="ck_product_cost_entries_cost_nonnegative"),
        CheckConstraint(
            "pieces_per_box IS NULL OR pieces_per_box > 0",
            name="ck_product_cost_entries_piece_count_positive",
        ),
        CheckConstraint(
            "cost_basis != 'BOX' OR pieces_per_box IS NOT NULL",
            name="ck_product_cost_entries_box_has_piece_count",
        ),
        Index(
            "ix_product_cost_entries_latest",
            "tenant_id",
            "tenant_product_id",
            "supplier_id",
            "currency",
            "cost_basis",
            "effective_at",
            "created_at",
            "id",
        ),
    )


class InvoiceSequence(Base):
    __tablename__ = "invoice_sequences"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("year BETWEEN 2000 AND 9999", name="ck_invoice_sequences_year_range"),
        CheckConstraint("last_number >= 0", name="ck_invoice_sequences_last_number_nonnegative"),
    )


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    customer_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    official_invoice_number: Mapped[str | None] = mapped_column(String(11))
    official_invoice_year: Mapped[int | None] = mapped_column(Integer)
    official_sequence_number: Mapped[int | None] = mapped_column(Integer)
    current_revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    confirmed_revision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[InvoiceStatus] = mapped_column(
        invoice_status_enum,
        default=InvoiceStatus.DRAFT,
        server_default="DRAFT",
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_invoices_customer_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_invoices_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "official_invoice_number",
            name="uq_invoices_tenant_official_number",
        ),
        UniqueConstraint(
            "tenant_id",
            "official_invoice_year",
            "official_sequence_number",
            name="uq_invoices_tenant_year_sequence",
        ),
        ForeignKeyConstraint(
            ["current_revision_id", "tenant_id", "id"],
            ["invoice_revisions.id", "invoice_revisions.tenant_id", "invoice_revisions.invoice_id"],
            name="fk_invoices_current_revision_scope",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["confirmed_revision_id", "tenant_id", "id"],
            ["invoice_revisions.id", "invoice_revisions.tenant_id", "invoice_revisions.invoice_id"],
            name="fk_invoices_confirmed_revision_scope",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "(official_invoice_number IS NULL AND official_invoice_year IS NULL "
            "AND official_sequence_number IS NULL) OR "
            "(official_invoice_number IS NOT NULL AND official_invoice_year IS NOT NULL "
            "AND official_sequence_number IS NOT NULL)",
            name="ck_invoices_official_number_complete",
        ),
        CheckConstraint(
            "official_invoice_year IS NULL OR official_invoice_year BETWEEN 2000 AND 9999",
            name="ck_invoices_official_year_range",
        ),
        CheckConstraint(
            "official_sequence_number IS NULL OR official_sequence_number > 0",
            name="ck_invoices_official_sequence_positive",
        ),
        Index(
            "ix_invoices_tenant_order_unique",
            "tenant_id",
            "order_id",
            unique=True,
            postgresql_where=order_id.is_not(None),
        ),
    )


class InvoiceRevision(Base):
    __tablename__ = "invoice_revisions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    client_command_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    predecessor_revision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    server_revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    customer_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prior_balance_snapshot: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    markup_total: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    net_sales: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    amount_due_display: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "tenant_id"],
            ["invoices.id", "invoices.tenant_id"],
            ondelete="CASCADE",
            name="fk_invoice_revisions_invoice_tenant",
        ),
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_invoice_revisions_customer_tenant",
        ),
        ForeignKeyConstraint(
            ["predecessor_revision_id", "tenant_id", "invoice_id"],
            ["invoice_revisions.id", "invoice_revisions.tenant_id", "invoice_revisions.invoice_id"],
            ondelete="RESTRICT",
            name="fk_invoice_revisions_predecessor_scope",
        ),
        UniqueConstraint(
            "id", "tenant_id", "invoice_id", name="uq_invoice_revisions_identity_scope"
        ),
        UniqueConstraint("id", "tenant_id", name="uq_invoice_revisions_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "invoice_id",
            "client_command_id",
            name="uq_invoice_revisions_client_command",
        ),
        UniqueConstraint(
            "tenant_id",
            "invoice_id",
            "server_revision_number",
            name="uq_invoice_revisions_server_number",
        ),
        Index(
            "uq_invoice_revisions_create_command",
            "tenant_id",
            "client_command_id",
            unique=True,
            postgresql_where=text("predecessor_revision_id IS NULL"),
        ),
        Index(
            "ix_invoice_revisions_one_successor",
            "tenant_id",
            "invoice_id",
            "predecessor_revision_id",
            unique=True,
            postgresql_where=predecessor_revision_id.is_not(None),
        ),
        CheckConstraint("server_revision_number > 0", name="ck_invoice_revisions_number_positive"),
        CheckConstraint("subtotal >= 0", name="ck_invoice_revisions_subtotal_nonnegative"),
        CheckConstraint("discount_total >= 0", name="ck_invoice_revisions_discount_nonnegative"),
        CheckConstraint("markup_total >= 0", name="ck_invoice_revisions_markup_nonnegative"),
        CheckConstraint("net_sales >= 0", name="ck_invoice_revisions_net_sales_nonnegative"),
    )


class InvoiceRevisionItem(Base):
    __tablename__ = "invoice_revision_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_product_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64))
    media_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    price_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    pieces_per_box: Mapped[int | None] = mapped_column(Integer)
    normal_unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    grade_rule_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    effective_unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    line_discount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    line_markup: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    customer_grade: Mapped[CustomerGrade | None] = mapped_column(customer_grade_enum)
    price_source: Mapped[PriceResolutionSource] = mapped_column(
        price_resolution_source_enum,
        default=PriceResolutionSource.NORMAL,
        server_default="NORMAL",
        nullable=False,
    )
    grade_discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    supplier_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    product_cost_entry_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    cost_currency: Mapped[str | None] = mapped_column(String(3))
    cost_basis: Mapped[ProductPriceBasis | None] = mapped_column(product_price_basis_enum)
    cost_pieces_per_box: Mapped[int | None] = mapped_column(Integer)
    cost_source_type: Mapped[str | None] = mapped_column(String(40))
    is_cost_override: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    cost_override_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_revision_id", "tenant_id"],
            ["invoice_revisions.id", "invoice_revisions.tenant_id"],
            ondelete="CASCADE",
            name="fk_invoice_revision_items_revision_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_invoice_revision_items_product_tenant",
        ),
        ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_invoice_revision_items_supplier_tenant",
        ),
        ForeignKeyConstraint(
            ["product_cost_entry_id", "tenant_id", "tenant_product_id", "supplier_id"],
            [
                "tenant_product_cost_entries.id",
                "tenant_product_cost_entries.tenant_id",
                "tenant_product_cost_entries.tenant_product_id",
                "tenant_product_cost_entries.supplier_id",
            ],
            ondelete="RESTRICT",
            name="fk_invoice_revision_items_cost_source_scope",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_invoice_revision_items_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "invoice_revision_id",
            "line_number",
            name="uq_invoice_revision_items_line_number",
        ),
        CheckConstraint("line_number > 0", name="ck_invoice_revision_items_line_number_positive"),
        CheckConstraint("quantity > 0", name="ck_invoice_revision_items_quantity_positive"),
        CheckConstraint(
            "normal_unit_price >= 0", name="ck_invoice_revision_items_normal_price_nonnegative"
        ),
        CheckConstraint(
            "effective_unit_price >= 0",
            name="ck_invoice_revision_items_effective_price_nonnegative",
        ),
        CheckConstraint(
            "line_discount >= 0", name="ck_invoice_revision_items_discount_nonnegative"
        ),
        CheckConstraint("line_markup >= 0", name="ck_invoice_revision_items_markup_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_invoice_revision_items_total_nonnegative"),
        CheckConstraint(
            "pieces_per_box IS NULL OR pieces_per_box > 0",
            name="ck_invoice_revision_items_piece_count_positive",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_invoice_revision_items_cost_nonnegative",
        ),
        CheckConstraint(
            "cost_pieces_per_box IS NULL OR cost_pieces_per_box > 0",
            name="ck_invoice_revision_items_cost_piece_count_positive",
        ),
        CheckConstraint(
            "(unit_cost IS NULL AND cost_currency IS NULL AND cost_basis IS NULL "
            "AND cost_source_type IS NULL) OR "
            "(unit_cost IS NOT NULL AND cost_currency IS NOT NULL AND cost_basis IS NOT NULL "
            "AND cost_source_type IS NOT NULL)",
            name="ck_invoice_revision_items_cost_snapshot_complete",
        ),
        CheckConstraint(
            "(NOT is_cost_override AND cost_override_reason IS NULL) OR "
            "(is_cost_override AND unit_cost IS NOT NULL "
            "AND length(btrim(coalesce(cost_override_reason, ''))) > 0)",
            name="ck_invoice_revision_items_override_reason",
        ),
        CheckConstraint(
            "grade_discount_percent IS NULL OR "
            "(grade_discount_percent >= 0 AND grade_discount_percent <= 100)",
            name="ck_invoice_revision_items_grade_discount_percent_range",
        ),
    )


class CustomerLedgerEntry(Base):
    __tablename__ = "customer_ledger_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    signed_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    entry_type: Mapped[LedgerEntryType] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_effect_key: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reverses_entry_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_customer_ledger_customer_tenant",
        ),
        ForeignKeyConstraint(
            ["reverses_entry_id", "tenant_id"],
            ["customer_ledger_entries.id", "customer_ledger_entries.tenant_id"],
            ondelete="RESTRICT",
            name="fk_customer_ledger_reversal_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_customer_ledger_id_tenant"),
        UniqueConstraint(
            "id",
            "tenant_id",
            "currency",
            "customer_id",
            name="uq_customer_ledger_allocation_scope",
        ),
        UniqueConstraint("tenant_id", "source_effect_key", name="uq_customer_ledger_source_effect"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_customer_ledger_idempotency"),
        UniqueConstraint(
            "tenant_id", "reverses_entry_id", name="uq_customer_ledger_single_reversal"
        ),
        CheckConstraint(
            "signed_amount <> 0 OR entry_type IN ('INVOICE_ADJUSTMENT', 'INVOICE_REVERSAL')",
            name="ck_customer_ledger_amount_nonzero",
        ),
        CheckConstraint(
            "entry_type <> 'OPENING_BALANCE_CORRECTION' OR reverses_entry_id IS NOT NULL",
            name="ck_customer_ledger_opening_correction_link",
        ),
        Index(
            "uq_customer_ledger_one_opening",
            "tenant_id",
            "customer_id",
            "currency",
            unique=True,
            postgresql_where=text("entry_type = 'OPENING_BALANCE'"),
        ),
        Index(
            "ix_customer_ledger_balance",
            "tenant_id",
            "customer_id",
            "currency",
            "effective_at",
            "created_at",
            "id",
        ),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    supplier_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    direction: Mapped[PaymentDirection] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str | None] = mapped_column(String(80))
    reference: Mapped[str | None] = mapped_column(String(200))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    source_device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reverses_payment_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_payments_customer_tenant",
        ),
        ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_payments_supplier_tenant",
        ),
        ForeignKeyConstraint(
            ["reverses_payment_id", "tenant_id"],
            ["payments.id", "payments.tenant_id"],
            ondelete="RESTRICT",
            name="fk_payments_reversal_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_payments_id_tenant"),
        UniqueConstraint(
            "id", "tenant_id", "currency", "customer_id", name="uq_payments_customer_scope"
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_payments_idempotency"),
        UniqueConstraint("tenant_id", "reverses_payment_id", name="uq_payments_single_reversal"),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint(
            "((direction IN ('CUSTOMER_RECEIPT', 'CUSTOMER_RECEIPT_REVERSAL', "
            "'CUSTOMER_REFUND')) AND customer_id IS NOT NULL AND supplier_id IS NULL) OR "
            "((direction IN ('SUPPLIER_PAYMENT', 'SUPPLIER_PAYMENT_REVERSAL')) "
            "AND supplier_id IS NOT NULL AND customer_id IS NULL)",
            name="ck_payments_party_matches_direction",
        ),
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_ledger_entry_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    kind: Mapped[AllocationKind] = mapped_column(String(20), nullable=False)
    reverses_allocation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_id", "tenant_id", "currency", "customer_id"],
            ["payments.id", "payments.tenant_id", "payments.currency", "payments.customer_id"],
            ondelete="RESTRICT",
            name="fk_payment_allocations_payment_scope",
        ),
        ForeignKeyConstraint(
            ["target_ledger_entry_id", "tenant_id", "currency", "customer_id"],
            [
                "customer_ledger_entries.id",
                "customer_ledger_entries.tenant_id",
                "customer_ledger_entries.currency",
                "customer_ledger_entries.customer_id",
            ],
            ondelete="RESTRICT",
            name="fk_payment_allocations_target_scope",
        ),
        ForeignKeyConstraint(
            ["reverses_allocation_id", "tenant_id"],
            ["payment_allocations.id", "payment_allocations.tenant_id"],
            ondelete="RESTRICT",
            name="fk_payment_allocations_reversal_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_payment_allocations_id_tenant"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_payment_allocations_idempotency"),
        UniqueConstraint(
            "tenant_id",
            "reverses_allocation_id",
            name="uq_payment_allocations_single_reversal",
        ),
        CheckConstraint("amount > 0", name="ck_payment_allocations_amount_positive"),
        CheckConstraint(
            "(kind = 'APPLY' AND reverses_allocation_id IS NULL) OR "
            "(kind = 'REVERSAL' AND reverses_allocation_id IS NOT NULL)",
            name="ck_payment_allocations_reversal_shape",
        ),
    )


class SupplierLedgerEntry(Base):
    __tablename__ = "supplier_ledger_entries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    signed_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    entry_type: Mapped[SupplierLedgerEntryType] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_effect_key: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reverses_entry_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_supplier_ledger_supplier_tenant",
        ),
        ForeignKeyConstraint(
            ["reverses_entry_id", "tenant_id"],
            ["supplier_ledger_entries.id", "supplier_ledger_entries.tenant_id"],
            ondelete="RESTRICT",
            name="fk_supplier_ledger_reversal_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_supplier_ledger_id_tenant"),
        UniqueConstraint("tenant_id", "source_effect_key", name="uq_supplier_ledger_source_effect"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_supplier_ledger_idempotency"),
        UniqueConstraint(
            "tenant_id", "reverses_entry_id", name="uq_supplier_ledger_single_reversal"
        ),
        CheckConstraint("signed_amount <> 0", name="ck_supplier_ledger_amount_nonzero"),
        CheckConstraint(
            "entry_type <> 'OPENING_BALANCE_CORRECTION' OR reverses_entry_id IS NOT NULL",
            name="ck_supplier_ledger_opening_correction_link",
        ),
        Index(
            "uq_supplier_ledger_one_opening",
            "tenant_id",
            "supplier_id",
            "currency",
            unique=True,
            postgresql_where=text("entry_type = 'OPENING_BALANCE'"),
        ),
        Index(
            "ix_supplier_ledger_balance",
            "tenant_id",
            "supplier_id",
            "currency",
            "effective_at",
            "created_at",
            "id",
        ),
    )


class PublicInvoiceCapability(TimestampMixin, Base):
    __tablename__ = "public_invoice_capabilities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_from_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "tenant_id"],
            ["invoices.id", "invoices.tenant_id"],
            ondelete="CASCADE",
            name="fk_public_invoice_capabilities_invoice_tenant",
        ),
        ForeignKeyConstraint(
            ["rotated_from_id", "tenant_id"],
            ["public_invoice_capabilities.id", "public_invoice_capabilities.tenant_id"],
            ondelete="RESTRICT",
            name="fk_public_invoice_capabilities_rotation_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_public_invoice_capabilities_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "rotated_from_id",
            name="uq_public_invoice_capabilities_single_rotation",
        ),
        CheckConstraint(
            "length(token_sha256) = 64", name="ck_public_invoice_capabilities_hash_length"
        ),
    )


class SyncDevice(Base):
    __tablename__ = "sync_devices"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_memberships.id", ondelete="CASCADE"), nullable=False
    )
    device_installation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    protocol_version: Mapped[int] = mapped_column(Integer, nullable=False)
    app_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_acknowledged_change_seq: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0"), default=0
    )
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_sync_devices_id_tenant"),
        Index(
            "uq_sync_devices_active_installation",
            "tenant_id",
            "user_id",
            "device_installation_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class SyncChange(Base):
    __tablename__ = "sync_changes"

    change_seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    operation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    device_installation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("operation IN ('upsert', 'delete')", name="ck_sync_changes_operation"),
        Index("ix_sync_changes_tenant_seq", "tenant_id", "change_seq"),
        Index("ix_sync_changes_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )


class SyncOperation(Base):
    __tablename__ = "sync_operations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_installation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('applied', 'rejected', 'conflict')", name="ck_sync_operations_status"
        ),
        UniqueConstraint(
            "tenant_id",
            "device_installation_id",
            "operation_id",
            name="uq_sync_operations_command",
        ),
    )


class TenantBackupConnection(Base):
    """A connected owner Drive folder (D-055). The refresh token is stored wrapped only."""

    __tablename__ = "tenant_backup_connections"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="google_drive")
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)
    folder_id: Mapped[str] = mapped_column(String(200), nullable=False)
    folder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    scopes: Mapped[str] = mapped_column(String(400), nullable=False)
    wrapped_refresh_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kek_id: Mapped[str] = mapped_column(String(80), nullable=False)
    connected_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(400))

    __table_args__ = (
        CheckConstraint("provider IN ('google_drive')", name="ck_backup_connections_provider"),
        Index(
            "uq_tenant_backup_connections_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("disconnected_at IS NULL"),
        ),
    )


class TenantBackupKey(Base):
    """Per-tenant data encryption key, wrapped by the environment master key (D-057)."""

    __tablename__ = "tenant_backup_keys"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kek_id: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantBackup(Base):
    __tablename__ = "tenant_backups"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    key_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant_backup_keys.id", ondelete="RESTRICT")
    )
    file_name: Mapped[str | None] = mapped_column(String(200))
    remote_file_id: Mapped[str | None] = mapped_column(String(200))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    checksum: Mapped[str | None] = mapped_column(String(64))
    manifest: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    error: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("kind IN ('DAILY', 'MONTHLY', 'MANUAL')", name="ck_backups_kind"),
        CheckConstraint(
            "status IN ('RUNNING', 'UPLOADED', 'FAILED', 'DELETED')", name="ck_backups_status"
        ),
        Index("ix_tenant_backups_tenant_created", "tenant_id", "created_at"),
    )


class TenantBackupRestore(Base):
    """A restore drill (VERIFY) or a controlled import into an empty tenant (IMPORT)."""

    __tablename__ = "tenant_backup_restores"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    backup_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_backups.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    report: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'")
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("mode IN ('VERIFY', 'IMPORT')", name="ck_backup_restores_mode"),
        CheckConstraint(
            "status IN ('VERIFIED', 'IMPORTED', 'FAILED')", name="ck_backup_restores_status"
        ),
    )


class ProductInteraction(Base):
    """A pseudonymous storefront view (D-062). Never an identity; session ids are hashed."""

    __tablename__ = "product_interactions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    tenant_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_products.id", ondelete="CASCADE"), nullable=False
    )
    session_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="VIEW")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('VIEW')", name="ck_product_interactions_kind"),
        Index(
            "ix_product_interactions_dedupe",
            "tenant_id",
            "tenant_product_id",
            "session_key",
            "occurred_at",
        ),
        Index("ix_product_interactions_tenant_occurred", "tenant_id", "occurred_at"),
    )


class ProductInteractionRollup(Base):
    """Monthly view counts after the 90-day raw retention (D-051); no session keys."""

    __tablename__ = "product_interaction_rollups"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_products.id", ondelete="CASCADE"), primary_key=True
    )
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class FeaturedCampaign(Base):
    """Owner-chosen featured product window (PHASE_05.md K). Advertising, never availability."""

    __tablename__ = "featured_campaigns"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    tenant_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_products.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_featured_campaigns_interval"),
        Index("ix_featured_campaigns_tenant_window", "tenant_id", "starts_at", "ends_at"),
    )


class CustomerAccessLink(Base):
    """Owner-issued personalized storefront link (D-071): hash-only, one active per customer."""

    __tablename__ = "customer_access_links"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(40))
    rotated_from_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_customer_access_links_tenant_customer", "tenant_id", "customer_id"),
        Index(
            "uq_customer_access_links_active",
            "tenant_id",
            "customer_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class Order(Base):
    """Storefront guest order (PHASE_05.md E/G). `intended_customer_id` is a hint (D-072)."""

    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="RECEIVED", server_default="RECEIVED"
    )
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_phone_raw: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_address: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    intended_customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL")
    )
    intended_assurance: Mapped[str | None] = mapped_column(String(12))
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_note: Mapped[str | None] = mapped_column(String(500))
    # P5-M5: the owner's explicit customer link and the tenant-local delivery date.
    linked_customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL", name="fk_orders_linked_customer")
    )
    delivery_date: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint(
            "status IN ('RECEIVED', 'CONFIRMED', 'DECLINED', 'CANCELLED')", name="ck_orders_status"
        ),
        CheckConstraint(
            "intended_assurance IS NULL OR intended_assurance IN ('LINK')",
            name="ck_orders_intended_assurance",
        ),
        Index("ix_orders_tenant_status_created", "tenant_id", "status", "created_at"),
    )


class CheckoutIdempotency(Base):
    __tablename__ = "checkout_idempotency"

    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    response: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrderAccessReference(Base):
    """Short-lived provisional reference bound to one checkout (D-046); never a D-042 link."""

    __tablename__ = "order_access_references"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_order_access_references_order", "tenant_id", "order_id"),)


class OwnerNotification(Base):
    """In-app owner notification; exactly one per accepted checkout (D-049)."""

    __tablename__ = "owner_notifications"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_owner_notifications_tenant_created", "tenant_id", "created_at"),
        Index(
            "uq_owner_notifications_order_received",
            "tenant_id",
            "order_id",
            unique=True,
            postgresql_where=text("order_id IS NOT NULL AND kind = 'ORDER_RECEIVED'"),
        ),
    )


class DeliveryReminder(Base):
    """Transactional reminder job for a confirmed order's delivery date (PHASE_05.md I)."""

    __tablename__ = "delivery_reminders"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="SCHEDULED", server_default="SCHEDULED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('SCHEDULED', 'SENT', 'CANCELLED')", name="ck_delivery_reminders_status"
        ),
        Index("ix_delivery_reminders_due", "status", "remind_at"),
    )


class OrderCancellationRequest(Base):
    """Customer cancellation *request* (PHASE_05.md J); the owner decides."""

    __tablename__ = "order_cancellation_requests"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, default="PENDING", server_default="PENDING"
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decision_note: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_order_cancellation_requests_status",
        ),
        Index("ix_order_cancellation_requests_order", "tenant_id", "order_id"),
        Index(
            "uq_order_cancellation_requests_pending",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )


class ProcurementStatus(StrEnum):
    """D-058 lifecycle. COMPLETE and CANCELLED are terminal."""

    OPEN = "OPEN"
    PARTIALLY_PURCHASED = "PARTIALLY_PURCHASED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class ProcurementItemOrigin(StrEnum):
    DEMAND = "DEMAND"
    MANUAL = "MANUAL"
    CARRY_FORWARD = "CARRY_FORWARD"


class ProcurementList(Base):
    """A purchasing to-do built from confirmed customer demand (PHASE_06.md E/F). Quantities
    are demand and progress only — never stock. The assignee is any active membership."""

    __tablename__ = "procurement_lists"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="OPEN", server_default="OPEN"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    demand_from: Mapped[date | None] = mapped_column(Date)
    demand_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(1000))
    assignee_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant_memberships.id", ondelete="SET NULL")
    )
    carried_from_list_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("procurement_lists.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_procurement_lists_id_tenant"),
        CheckConstraint(
            "status IN ('OPEN', 'PARTIALLY_PURCHASED', 'COMPLETE', 'CANCELLED')",
            name="ck_procurement_lists_status",
        ),
        CheckConstraint(
            "demand_from IS NULL OR demand_to IS NULL OR demand_from <= demand_to",
            name="ck_procurement_lists_demand_range",
        ),
        Index("ix_procurement_lists_tenant_status", "tenant_id", "status"),
        Index("ix_procurement_lists_assignee", "tenant_id", "assignee_membership_id"),
    )


class ProcurementItem(Base):
    """One product line. required = confirmed demand, target = owner-adjusted, purchased =
    progress written by supplier purchases; remaining is derived. Never deleted."""

    __tablename__ = "procurement_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    list_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    tenant_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    price_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    pieces_per_box: Mapped[int | None] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    required_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    target_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    purchased_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    demand_invoice_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remove_reason: Mapped[str | None] = mapped_column(String(300))
    waived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    waive_reason: Mapped[str | None] = mapped_column(String(300))
    carried_from_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("procurement_items.id", ondelete="SET NULL")
    )
    carried_to_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("procurement_items.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["list_id", "tenant_id"],
            ["procurement_lists.id", "procurement_lists.tenant_id"],
            ondelete="CASCADE",
            name="fk_procurement_items_list_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_procurement_items_product_tenant",
        ),
        ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="SET NULL",
            name="fk_procurement_items_supplier_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_procurement_items_id_tenant"),
        CheckConstraint(
            "origin IN ('DEMAND', 'MANUAL', 'CARRY_FORWARD')", name="ck_procurement_items_origin"
        ),
        CheckConstraint("required_quantity >= 0", name="ck_procurement_items_required_nonneg"),
        CheckConstraint("target_quantity >= 0", name="ck_procurement_items_target_nonneg"),
        CheckConstraint("purchased_quantity >= 0", name="ck_procurement_items_purchased_nonneg"),
        CheckConstraint(
            "(waived_at IS NULL) = (waive_reason IS NULL)", name="ck_procurement_items_waive_pair"
        ),
        CheckConstraint(
            "(removed_at IS NULL) = (remove_reason IS NULL)",
            name="ck_procurement_items_remove_pair",
        ),
        Index("ix_procurement_items_list", "tenant_id", "list_id"),
        Index("ix_procurement_items_product", "tenant_id", "tenant_product_id"),
    )

    @property
    def remaining_quantity(self) -> Decimal:
        remaining = Decimal(self.target_quantity) - Decimal(self.purchased_quantity)
        return max(Decimal("0"), remaining).quantize(Decimal("0.0001"))


class SupplierPurchase(Base):
    """Immutable actual purchase from a supplier (PHASE_06.md G). Finalization writes the
    ACTUAL_PURCHASE cost entries, one PURCHASE_CHARGE ledger entry and the procurement progress in
    the same transaction; a reversal is a compensating ledger entry plus `reversed_at`."""

    __tablename__ = "supplier_purchases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    procurement_list_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_reason: Mapped[str | None] = mapped_column(String(500))
    reversal_idempotency_key: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["supplier_id", "tenant_id"],
            ["tenant_suppliers.id", "tenant_suppliers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_supplier_purchases_supplier_tenant",
        ),
        ForeignKeyConstraint(
            ["procurement_list_id", "tenant_id"],
            ["procurement_lists.id", "procurement_lists.tenant_id"],
            ondelete="SET NULL",
            name="fk_supplier_purchases_list_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_supplier_purchases_id_tenant"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_supplier_purchases_idempotency"),
        CheckConstraint("total_amount >= 0", name="ck_supplier_purchases_total_nonneg"),
        CheckConstraint(
            "(reversed_at IS NULL) = (reversal_reason IS NULL)",
            name="ck_supplier_purchases_reversal_pair",
        ),
        Index("ix_supplier_purchases_supplier", "tenant_id", "supplier_id", "purchased_at"),
    )


class SupplierPurchaseItem(Base):
    __tablename__ = "supplier_purchase_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    purchase_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    procurement_item_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    price_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    pieces_per_box: Mapped[int | None] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cost_entry_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        ForeignKeyConstraint(
            ["purchase_id", "tenant_id"],
            ["supplier_purchases.id", "supplier_purchases.tenant_id"],
            ondelete="CASCADE",
            name="fk_supplier_purchase_items_purchase_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_supplier_purchase_items_product_tenant",
        ),
        ForeignKeyConstraint(
            ["procurement_item_id", "tenant_id"],
            ["procurement_items.id", "procurement_items.tenant_id"],
            ondelete="SET NULL",
            name="fk_supplier_purchase_items_procurement_tenant",
        ),
        ForeignKeyConstraint(
            ["cost_entry_id"],
            ["tenant_product_cost_entries.id"],
            ondelete="SET NULL",
            name="fk_supplier_purchase_items_cost_entry",
        ),
        UniqueConstraint("purchase_id", "line_number", name="uq_supplier_purchase_items_line"),
        CheckConstraint("quantity > 0", name="ck_supplier_purchase_items_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_supplier_purchase_items_unit_cost_nonneg"),
        CheckConstraint("line_total >= 0", name="ck_supplier_purchase_items_total_nonneg"),
        Index("ix_supplier_purchase_items_purchase", "tenant_id", "purchase_id"),
    )


class DeliveryTaskStatus(StrEnum):
    """D-063: both end states are terminal; a mistaken completion gets a new task."""

    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DeliveryTask(Base):
    """One delivery of one CONFIRMED invoice by one active membership (PHASE_07.md A/B).
    Tasks never create, recalculate or cancel invoices; `amount_to_collect` is a projection."""

    __tablename__ = "delivery_tasks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    assigned_membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenant_memberships.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default="ASSIGNED", server_default="ASSIGNED"
    )
    delivery_date: Mapped[date | None] = mapped_column(Date)
    route_sequence: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_to_collect: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performed_by_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenant_memberships.id", ondelete="SET NULL")
    )
    completion_note: Mapped[str | None] = mapped_column(String(500))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1"), default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_delivery_tasks_customer_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_delivery_tasks_id_tenant"),
        CheckConstraint(
            "status IN ('ASSIGNED', 'COMPLETED', 'CANCELLED')", name="ck_delivery_tasks_status"
        ),
        CheckConstraint(
            "(completed_at IS NULL) = (performed_by_membership_id IS NULL)",
            name="ck_delivery_tasks_completion_pair",
        ),
        CheckConstraint(
            "(cancelled_at IS NULL) = (cancel_reason IS NULL)",
            name="ck_delivery_tasks_cancel_pair",
        ),
        CheckConstraint("amount_to_collect >= 0", name="ck_delivery_tasks_amount_nonneg"),
        Index("ix_delivery_tasks_tenant_date_status", "tenant_id", "delivery_date", "status"),
        Index("ix_delivery_tasks_assignee", "tenant_id", "assigned_membership_id"),
        Index(
            "uq_delivery_tasks_open_invoice",
            "invoice_id",
            unique=True,
            postgresql_where=text("status = 'ASSIGNED'"),
        ),
    )
