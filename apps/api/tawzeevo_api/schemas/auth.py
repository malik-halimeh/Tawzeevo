from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from tawzeevo_api.models import SystemUserType
from tawzeevo_api.phone import InvalidPhoneNumberError, normalize_phone


def normalize_required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must contain non-whitespace characters")
    return normalized


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: EmailStr
    phone: str = Field(max_length=64)
    city: str = Field(max_length=120)
    age: int = Field(ge=1, le=120)
    password: SecretStr

    @field_validator("first_name", "last_name", "city", mode="before")
    @classmethod
    def validate_required_text(cls, value: object, info: object) -> str:
        field_name = getattr(info, "field_name", "field")
        return normalize_required_text(value, field_name)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value).strip().lower()
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        raw_value = value.strip()
        try:
            normalize_phone(raw_value)
        except InvalidPhoneNumberError as exc:
            raise ValueError(str(exc)) from exc
        return raw_value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not 10 <= len(password) <= 128:
            raise ValueError("Password must contain between 10 and 128 characters")
        if not password.strip():
            raise ValueError("Password must not be empty or all-whitespace")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value).strip().lower()
        return value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    city: str
    age: int
    type: SystemUserType
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
