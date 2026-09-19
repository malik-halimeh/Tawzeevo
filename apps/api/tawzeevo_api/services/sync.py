"""Sync device registry and authorized bootstrap (PHASE_04.md C/G; D-052, D-054).

A device registers only during an authenticated bootstrap by an active tenant owner. The device
installation id is a deduplication identity, never authorization: every call still validates the
session, membership and tenant lifecycle through the normal dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    Category,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    Payment,
    SyncChange,
    SyncDevice,
    Tenant,
    TenantBarcode,
    TenantMembership,
    TenantProduct,
    TenantRole,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope
from tawzeevo_api.schemas.sync import (
    BootstrapRequest,
    BootstrapResponse,
    ChangeRecord,
    DeviceResponse,
    PullResponse,
    SnapshotPageResponse,
)
from tawzeevo_api.services import sync_changes
from tawzeevo_api.services.sync_changes import APP_SCHEMA_VERSION, PROTOCOL_VERSION

PULL_PAGE_SIZE = 500  # D-052
OFFLINE_LEASE = timedelta(hours=24)  # D-054
DEVICE_RETIREMENT = timedelta(days=90)  # D-054
TOMBSTONE_RETENTION = timedelta(days=90)  # D-053

_SNAPSHOT_SOURCES: dict[str, tuple[type[Any], Callable[[Any], dict[str, Any]]]] = {
    "customers": (Customer, sync_changes.PROJECTIONS[Customer][1]),
    "categories": (Category, sync_changes.PROJECTIONS[Category][1]),
    "tenant_products": (TenantProduct, sync_changes.PROJECTIONS[TenantProduct][1]),
    "tenant_barcodes": (TenantBarcode, sync_changes.PROJECTIONS[TenantBarcode][1]),
    "invoices": (Invoice, sync_changes.PROJECTIONS[Invoice][1]),
    "invoice_revisions": (InvoiceRevision, sync_changes.PROJECTIONS[InvoiceRevision][1]),
    "invoice_revision_items": (
        InvoiceRevisionItem,
        sync_changes.PROJECTIONS[InvoiceRevisionItem][1],
    ),
    "payments": (Payment, sync_changes.PROJECTIONS[Payment][1]),
    "customer_ledger_entries": (
        CustomerLedgerEntry,
        sync_changes.PROJECTIONS[CustomerLedgerEntry][1],
    ),
}


def high_water(db: Session, tenant_id: UUID) -> int:
    value = db.scalar(
        select(func.coalesce(func.max(SyncChange.change_seq), 0)).where(
            SyncChange.tenant_id == tenant_id
        )
    )
    return int(value or 0)


def _protocol_check(protocol_version: int, app_schema_version: int) -> None:
    if protocol_version != PROTOCOL_VERSION:
        raise AppError(
            409,
            "SYNC_PROTOCOL_MISMATCH",
            f"Sync protocol {protocol_version} is not supported; server speaks {PROTOCOL_VERSION}",
        )
    if app_schema_version > APP_SCHEMA_VERSION:
        raise AppError(
            409,
            "SYNC_SCHEMA_TOO_NEW",
            "This device schema is newer than the server; update the server first",
        )


def bootstrap(
    db: Session, tenant_id: UUID, membership: TenantMembership, request: BootstrapRequest
) -> BootstrapResponse:
    _protocol_check(request.protocol_version, request.app_schema_version)
    now = datetime.now(UTC)
    device = db.scalar(
        select(SyncDevice)
        .where(
            SyncDevice.tenant_id == tenant_id,
            SyncDevice.user_id == membership.user_id,
            SyncDevice.device_installation_id == request.device_installation_id,
            SyncDevice.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if device is None:
        device = SyncDevice(
            tenant_id=tenant_id,
            user_id=membership.user_id,
            membership_id=membership.id,
            device_installation_id=request.device_installation_id,
            protocol_version=request.protocol_version,
            app_schema_version=request.app_schema_version,
            lease_expires_at=now + OFFLINE_LEASE,
        )
        db.add(device)
    else:
        device.protocol_version = request.protocol_version
        device.app_schema_version = request.app_schema_version
        device.lease_expires_at = now + OFFLINE_LEASE
        device.last_seen_at = now
        # A fresh bootstrap restarts the cursor: the device will re-download the snapshot.
        device.last_acknowledged_change_seq = 0
    db.flush()
    water = high_water(db, tenant_id)
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(device)
    # PHASE_07.md D/I: a driver's device registers for the outbox but never downloads the owner
    # projection; its cache is fed only by the assigned-task change feed.
    collections = list(_SNAPSHOT_SOURCES) if membership.role is TenantRole.OWNER else []
    return BootstrapResponse(
        device=DeviceResponse.model_validate(device),
        high_water_change_seq=water,
        protocol_version=PROTOCOL_VERSION,
        app_schema_version=APP_SCHEMA_VERSION,
        collections=collections,
        page_size=PULL_PAGE_SIZE,
    )


def active_device(
    db: Session, tenant_id: UUID, membership: TenantMembership, device_installation_id: UUID
) -> SyncDevice:
    # The active registration wins; a retired/revoked twin only matters when no active one exists.
    device = db.scalar(
        select(SyncDevice)
        .where(
            SyncDevice.tenant_id == tenant_id,
            SyncDevice.user_id == membership.user_id,
            SyncDevice.device_installation_id == device_installation_id,
        )
        .order_by(SyncDevice.revoked_at.is_(None).desc(), SyncDevice.created_at.desc())
    )
    if device is None:
        raise AppError(404, "SYNC_DEVICE_NOT_REGISTERED", "Bootstrap this device first")
    if device.revoked_at is not None:
        raise AppError(403, "SYNC_DEVICE_REVOKED", "This device was revoked; re-bootstrap required")
    now = datetime.now(UTC)
    if device.last_seen_at < now - DEVICE_RETIREMENT:
        device.revoked_at = now
        device.revoked_reason = "RETIRED_UNSEEN"
        commit_and_restore_tenant_scope(db, tenant_id)
        raise AppError(410, "SYNC_REBOOTSTRAP_REQUIRED", "Device retired; bootstrap again")
    device.last_seen_at = now
    device.lease_expires_at = now + OFFLINE_LEASE
    return device


def snapshot_page(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    device_installation_id: UUID,
    collection: str,
    cursor: str | None,
    page_size: int,
) -> SnapshotPageResponse:
    source = _SNAPSHOT_SOURCES.get(collection)
    if source is None:
        raise AppError(404, "SYNC_COLLECTION_UNKNOWN", "Unknown snapshot collection")
    device = active_device(db, tenant_id, membership, device_installation_id)
    model, project = source
    page_size = max(1, min(page_size, PULL_PAGE_SIZE))
    query: Any = select(model).where(model.tenant_id == tenant_id).order_by(model.id.asc())
    if cursor:
        try:
            query = query.where(model.id > UUID(cursor))
        except ValueError as exc:
            raise AppError(400, "SYNC_CURSOR_INVALID", "Snapshot cursor is invalid") from exc
    rows = list(db.scalars(query.limit(page_size + 1)))
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    water = high_water(db, tenant_id)
    commit_and_restore_tenant_scope(db, tenant_id)  # persists last_seen/lease refresh
    _ = device
    return SnapshotPageResponse(
        collection=collection,
        items=[project(row) for row in rows],
        next_cursor=str(rows[-1].id) if has_more and rows else None,
        high_water_change_seq=water,
    )


def revoke_tenant_devices(db: Session, tenant_id: UUID, reason: str) -> int:
    """Revoke every active device of a tenant (suspension/closure). Caller commits."""
    now = datetime.now(UTC)
    count = 0
    for device in db.scalars(
        select(SyncDevice).where(SyncDevice.tenant_id == tenant_id, SyncDevice.revoked_at.is_(None))
    ):
        device.revoked_at = now
        device.revoked_reason = reason
        count += 1
    return count


def revoke_membership_devices(
    db: Session, tenant_id: UUID, membership_id: UUID, reason: str
) -> int:
    now = datetime.now(UTC)
    count = 0
    for device in db.scalars(
        select(SyncDevice).where(
            SyncDevice.tenant_id == tenant_id,
            SyncDevice.membership_id == membership_id,
            SyncDevice.revoked_at.is_(None),
        )
    ):
        device.revoked_at = now
        device.revoked_reason = reason
        count += 1
    return count


def pull_changes(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    device_installation_id: UUID,
    cursor: int,
    page_size: int,
) -> PullResponse:
    """Ordered change records after `cursor` (PHASE_04.md F pull; D-052/D-053).

    The cursor is also the device's acknowledgement: everything at or below it was applied.
    A cursor below the tenant's retention floor cannot be served incrementally.
    """
    device = active_device(db, tenant_id, membership, device_installation_id)
    tenant = db.get(Tenant, tenant_id)
    floor = int(tenant.sync_retention_floor) if tenant is not None else 0
    if cursor < floor:
        commit_and_restore_tenant_scope(db, tenant_id)
        raise AppError(
            410,
            "SYNC_REBOOTSTRAP_REQUIRED",
            "This device is older than the retained change history; bootstrap again",
        )
    page_size = max(1, min(page_size, PULL_PAGE_SIZE))
    rows = list(
        db.scalars(
            select(SyncChange)
            .where(SyncChange.tenant_id == tenant_id, SyncChange.change_seq > cursor)
            .order_by(SyncChange.change_seq.asc())
            .limit(page_size + 1)
        )
    )
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    next_cursor = rows[-1].change_seq if rows else cursor
    if membership.role is not TenantRole.OWNER:
        # Least privilege (PHASE_07.md D): drivers receive only their own delivery tasks. The
        # cursor still advances over everything so the feed stays ordered and acknowledged.
        rows = [
            row
            for row in rows
            if row.entity_type == "delivery_task"
            and str(row.payload.get("assigned_membership_id")) == str(membership.id)
        ]
    if cursor > device.last_acknowledged_change_seq:
        device.last_acknowledged_change_seq = cursor
    water = high_water(db, tenant_id)
    commit_and_restore_tenant_scope(db, tenant_id)
    return PullResponse(
        changes=[
            ChangeRecord(
                change_seq=row.change_seq,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                operation="delete" if row.operation == "delete" else "upsert",
                version=row.version,
                payload=row.payload,
                operation_id=row.operation_id,
                device_installation_id=row.device_installation_id,
                occurred_at=row.occurred_at,
            )
            for row in rows
        ],
        next_cursor=next_cursor,
        high_water_change_seq=water,
        has_more=has_more,
        protocol_version=PROTOCOL_VERSION,
    )


def purge_sync_changes(db: Session, tenant_id: UUID, *, now: datetime | None = None) -> int:
    """Delete change records older than the retention window that no active device still needs.

    D-053: tombstones are kept at least 90 days and longer while an active, non-retired device
    has not acknowledged past them. The tenant's retention floor records the highest purged
    sequence so stale devices are told to re-bootstrap instead of silently missing deletions.
    """
    now = now or datetime.now(UTC)
    cutoff = now - TOMBSTONE_RETENTION
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant was not found")
    slowest = db.scalar(
        select(func.min(SyncDevice.last_acknowledged_change_seq)).where(
            SyncDevice.tenant_id == tenant_id,
            SyncDevice.revoked_at.is_(None),
            SyncDevice.last_seen_at >= now - DEVICE_RETIREMENT,
        )
    )
    purgeable = select(SyncChange.change_seq).where(
        SyncChange.tenant_id == tenant_id, SyncChange.occurred_at < cutoff
    )
    if slowest is not None:
        purgeable = purgeable.where(SyncChange.change_seq <= int(slowest))
    seqs = list(db.scalars(purgeable))
    if not seqs:
        return 0
    highest = max(seqs)
    db.execute(
        delete(SyncChange).where(SyncChange.tenant_id == tenant_id, SyncChange.change_seq.in_(seqs))
    )
    if highest > int(tenant.sync_retention_floor):
        tenant.sync_retention_floor = highest
    commit_and_restore_tenant_scope(db, tenant_id)
    return len(seqs)
