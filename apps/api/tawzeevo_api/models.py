from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
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
    status: Mapped[TenantStatus] = mapped_column(
        tenant_status_enum, default=TenantStatus.ACTIVE, server_default="ACTIVE", nullable=False
    )
    access_until: Mapped[date | None] = mapped_column(Date)
    grace_until: Mapped[date | None] = mapped_column(Date)
    suspension_reason: Mapped[SuspensionReason | None] = mapped_column(suspension_reason_enum)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "grace_until IS NULL OR access_until IS NULL OR grace_until >= access_until",
            name="ck_tenants_grace_not_before_access",
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

    __table_args__ = (
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
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    pieces_per_box: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "tenant_id"],
            ["categories.id", "categories.tenant_id"],
            ondelete="RESTRICT",
            name="fk_tenant_products_category_tenant",
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


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        invoice_status_enum,
        default=InvoiceStatus.DRAFT,
        server_default="DRAFT",
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            ondelete="RESTRICT",
            name="fk_invoices_customer_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_invoices_id_tenant"),
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_nonnegative"),
    )


class InvoiceItem(TimestampMixin, Base):
    __tablename__ = "invoice_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    barcode: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    price_basis: Mapped[ProductPriceBasis] = mapped_column(product_price_basis_enum, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    customer_grade: Mapped[CustomerGrade | None] = mapped_column(customer_grade_enum)
    price_source: Mapped[PriceResolutionSource] = mapped_column(
        price_resolution_source_enum,
        default=PriceResolutionSource.NORMAL,
        server_default="NORMAL",
        nullable=False,
    )
    grade_discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))

    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "tenant_id"],
            ["invoices.id", "invoices.tenant_id"],
            ondelete="CASCADE",
            name="fk_invoice_items_invoice_tenant",
        ),
        ForeignKeyConstraint(
            ["product_id", "tenant_id"],
            ["tenant_products.id", "tenant_products.tenant_id"],
            ondelete="RESTRICT",
            name="fk_invoice_items_product_tenant",
        ),
        CheckConstraint("quantity > 0", name="ck_invoice_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_items_unit_price_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_invoice_items_line_total_nonnegative"),
        CheckConstraint(
            "grade_discount_percent IS NULL OR "
            "(grade_discount_percent >= 0 AND grade_discount_percent <= 100)",
            name="ck_invoice_items_grade_discount_percent_range",
        ),
    )
