from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tawzeevo_api.database import get_db
from tawzeevo_api.dependencies import TenantContext, require_tenant_owner
from tawzeevo_api.schemas.sync import (
    BootstrapRequest,
    BootstrapResponse,
    PushRequest,
    PushResponse,
    SnapshotCollection,
    SnapshotPageResponse,
)
from tawzeevo_api.services.sync import PULL_PAGE_SIZE, bootstrap, snapshot_page
from tawzeevo_api.services.sync_push import push_operations

sync_router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@sync_router.post("/bootstrap", response_model=BootstrapResponse)
def start_bootstrap(
    request: BootstrapRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> BootstrapResponse:
    """Register (or refresh) this device and return the change high-water mark to resume from."""
    return bootstrap(db, context.tenant.id, context.membership, request)


@sync_router.get("/bootstrap/{collection}", response_model=SnapshotPageResponse)
def read_snapshot_page(
    collection: SnapshotCollection,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
    device_installation_id: UUID,
    cursor: str | None = None,
    page_size: Annotated[int, Query(ge=1, le=PULL_PAGE_SIZE)] = PULL_PAGE_SIZE,
) -> SnapshotPageResponse:
    """One page of the authorized owner projection; resumable through the returned cursor."""
    return snapshot_page(
        db,
        context.tenant.id,
        context.membership,
        device_installation_id,
        collection,
        cursor,
        page_size,
    )


@sync_router.post("/push", response_model=PushResponse)
def push(
    request: PushRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[TenantContext, Depends(require_tenant_owner)],
) -> PushResponse:
    """Apply queued device operations exactly once; each operation is its own transaction."""
    return push_operations(db, context.tenant.id, context.membership, request)
