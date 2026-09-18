from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_system_admin, require_tenant_owner
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import User
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.schemas.backup import (
    AuthorizationUrlResponse,
    BackupConnectionResponse,
    BackupResponse,
    BackupStatusResponse,
    ConnectRequest,
    ImportRequest,
    RestoreResponse,
)
from tawzeevo_api.services import backup as backup_service
from tawzeevo_api.services.backup_drive import SCOPES

backup_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/backup", tags=["backup"])
platform_backup_router = APIRouter(prefix="/api/v1/platform", tags=["platform administration"])


@backup_router.get("", response_model=BackupStatusResponse)
def backup_status(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> BackupStatusResponse:
    """Connection, last backup, last restore drill and the retained history."""
    tenant_id = context.tenant.id
    backups = backup_service.list_backups(db, tenant_id)
    latest = next((b for b in backups if b.status == "UPLOADED"), None)
    connection = backup_service.active_connection(db, tenant_id)
    restore = backup_service.latest_restore(db, tenant_id)
    return BackupStatusResponse(
        connection=BackupConnectionResponse.model_validate(connection) if connection else None,
        latest_backup=BackupResponse.model_validate(latest) if latest else None,
        latest_restore=RestoreResponse.model_validate(restore) if restore else None,
        backups=[BackupResponse.model_validate(b) for b in backups],
        retention={
            "daily": backup_service.DAILY_RETENTION,
            "monthly": backup_service.MONTHLY_RETENTION,
        },
    )


@backup_router.post("/google/authorize", response_model=AuthorizationUrlResponse)
def google_authorize(
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> AuthorizationUrlResponse:
    """Where the owner grants `drive.file` access; the state binds the grant to this tenant."""
    url = backup_service.authorization_url(context.tenant.id, context.membership.user_id)
    return AuthorizationUrlResponse(authorization_url=url, scope=SCOPES)


@backup_router.post(
    "/google/connect",
    response_model=BackupConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def google_connect(
    request: ConnectRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> BackupConnectionResponse:
    connection = backup_service.connect(
        db, context.tenant, context.membership.user_id, request.code, request.state
    )
    return BackupConnectionResponse.model_validate(connection)


@backup_router.post("/google/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def google_disconnect(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> None:
    backup_service.disconnect(db, context.tenant.id, context.membership.user_id)


@backup_router.post("/run", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
def run_backup_now(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> BackupResponse:
    backup = backup_service.run_backup(db, context.tenant.id, context.membership.user_id, "MANUAL")
    return BackupResponse.model_validate(backup)


@backup_router.post("/{backup_id}/verify", response_model=RestoreResponse)
def verify_backup(
    backup_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> RestoreResponse:
    """Restore drill: download, decrypt and reconcile without touching live data."""
    record = backup_service.verify_backup(
        db, context.tenant.id, backup_id, context.membership.user_id
    )
    return RestoreResponse.model_validate(record)


@platform_backup_router.post(
    "/tenants/{tenant_id}/backups/{backup_id}/import", response_model=RestoreResponse
)
def import_backup(
    tenant_id: UUID,
    backup_id: UUID,
    request: ImportRequest,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_system_admin)],
) -> RestoreResponse:
    """Controlled import into an EMPTY tenant of the recovery environment (runbook step 6)."""
    if request.confirm_tenant_id != tenant_id:
        raise AppError(400, "BACKUP_IMPORT_CONFIRMATION", "confirm_tenant_id must equal the tenant")
    set_tenant_scope(db, tenant_id)
    record = backup_service.import_backup(db, tenant_id, backup_id, admin.id)
    return RestoreResponse.model_validate(record)
