from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BackupConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    account_email: str
    folder_name: str
    scopes: str
    connected_at: datetime
    last_error: str | None = None


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str
    scope: str


class ConnectRequest(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=2048)


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: Literal["DAILY", "MONTHLY", "MANUAL"]
    status: Literal["RUNNING", "UPLOADED", "FAILED", "DELETED"]
    file_name: str | None = None
    byte_size: int | None = None
    checksum: str | None = None
    manifest: dict[str, Any]
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    deleted_at: datetime | None = None


class RestoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    backup_id: UUID
    mode: Literal["VERIFY", "IMPORT"]
    status: Literal["VERIFIED", "IMPORTED", "FAILED"]
    report: dict[str, Any]
    created_at: datetime


class BackupStatusResponse(BaseModel):
    connection: BackupConnectionResponse | None
    latest_backup: BackupResponse | None
    latest_restore: RestoreResponse | None
    backups: list[BackupResponse]
    retention: dict[str, int]


class ImportRequest(BaseModel):
    """The administrator retypes the tenant id: the import is a deliberate, audited act."""

    confirm_tenant_id: UUID
