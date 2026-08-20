from __future__ import annotations

import unicodedata
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from tawzeevo_api.models import SystemUserType
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone
from tawzeevo_api.schemas.auth import RegisterRequest, UserResponse, normalize_required_text


def normalize_optional_text(value: object, field_name: str) -> object:
    if value is None:
        return value
    return normalize_required_text(value, field_name)


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, max_length=120)
    age: int | None = Field(default=None, ge=1, le=120)
    password: SecretStr | None = None

    @field_validator("first_name", "last_name", "city", mode="before")
    @classmethod
    def validate_optional_text(cls, value: object, info: object) -> object:
        return normalize_optional_text(value, getattr(info, "field_name", "field"))

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value).strip().lower()
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        raw_value = value.strip()
        try:
            normalize_phone(raw_value)
        except InvalidPhoneNumberError as exc:
            raise ValueError(str(exc)) from exc
        return raw_value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        password = value.get_secret_value()
        if not 10 <= len(password) <= 128:
            raise ValueError("Password must contain between 10 and 128 characters")
        if not password.strip():
            raise ValueError("Password must not be empty or all-whitespace")
        return value

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        null_fields = [
            field_name
            for field_name in self.model_fields_set
            if getattr(self, field_name, None) is None
        ]
        if null_fields:
            raise ValueError(f"Fields must not be null: {', '.join(sorted(null_fields))}")
        return self


class AdminCreateUserRequest(RegisterRequest):
    type: SystemUserType


class AdminUpdateUserRequest(ProfileUpdateRequest):
    type: SystemUserType | None = None


class UserListResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    users: list[UserResponse]


class UserCountResponse(BaseModel):
    count: int


class AverageAgeResponse(BaseModel):
    average_age: float | None


class CityCountResponse(BaseModel):
    city: str
    count: int


class UserPath(BaseModel):
    id: UUID
