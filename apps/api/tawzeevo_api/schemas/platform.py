from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tawzeevo_api.models import (
    SuspensionReason,
    TenantApplicationStatus,
    TenantStatus,
)
from tawzeevo_api.schemas.auth import normalize_required_text


class AccessState(StrEnum):
    CURRENT = "current"
    GRACE = "grace"
    OVERDUE = "overdue"


class TenantApplicationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(max_length=200)

    @field_validator("business_name", mode="before")
    @classmethod
    def validate_business_name(cls, value: object) -> str:
        return normalize_required_text(value, "business_name")


class TenantApplicationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("review_notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        if value is None:
            return None
        return normalize_required_text(value, "review_notes")


class TenantApplicationApproveRequest(TenantApplicationReviewRequest):
    access_until: date | None = None
    grace_until: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if (
            self.access_until is not None
            and self.grace_until is not None
            and self.grace_until < self.access_until
        ):
            raise ValueError("grace_until must not precede access_until")
        return self


class TenantApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    applicant_user_id: UUID
    business_name: str
    status: TenantApplicationStatus
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime


class TenantApplicationListResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    applications: list[TenantApplicationResponse]


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: TenantStatus
    access_until: date | None
    grace_until: date | None
    access_status: AccessState
    suspension_reason: SuspensionReason | None
    activated_at: datetime | None
    suspended_at: datetime | None
    reactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TenantListResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    tenants: list[TenantResponse]


class AccessPeriodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_until: date
    grace_until: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.grace_until is not None and self.grace_until < self.access_until:
            raise ValueError("grace_until must not precede access_until")
        return self


class SuspendTenantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: SuspensionReason = SuspensionReason.SUBSCRIPTION_OVERDUE


class ReactivateTenantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_until: date | None = None
    grace_until: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if (
            self.access_until is not None
            and self.grace_until is not None
            and self.grace_until < self.access_until
        ):
            raise ValueError("grace_until must not precede access_until")
        return self
