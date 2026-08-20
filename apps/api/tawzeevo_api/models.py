from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
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
