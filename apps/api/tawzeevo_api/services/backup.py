"""Encrypted Google backup lifecycle (PHASE_04.md L; D-055, D-056, D-057).

Connect (OAuth, `drive.file` only, one app-created folder per tenant) -> daily encrypted backup
with a clear-text manifest -> retention (30 daily, 12 monthly) -> restore drill (download,
decrypt, verify checksum and schema, reconcile counts) -> controlled import into an EMPTY tenant.
Nothing here ever writes into a live tenant, logs a token, or fabricates a key.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api import metrics
from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Tenant,
    TenantBackup,
    TenantBackupConnection,
    TenantBackupKey,
    TenantBackupRestore,
    TenantStatus,
)
from tawzeevo_api.repositories.tenancy import all_tenant_ids, set_tenant_scope
from tawzeevo_api.services import backup_crypto, backup_export
from tawzeevo_api.services.backup_drive import DriveClient, drive_client, oauth_client
from tawzeevo_api.services.sync import high_water

logger = logging.getLogger("tawzeevo.backup")

APP_VERSION = "0.1.0"
DAILY_RETENTION = 30
MONTHLY_RETENTION = 12
DAILY_INTERVAL = timedelta(hours=24)
STATE_TTL = timedelta(minutes=15)
STATE_AUDIENCE = "tawzeevo-backup-oauth"


def _now() -> datetime:
    return datetime.now(UTC)


def folder_name(tenant: Tenant) -> str:
    return f"Tawzeevo Backup – {tenant.name}"[:200]


# ---------------------------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------------------------


def active_connection(db: Session, tenant_id: UUID) -> TenantBackupConnection | None:
    return db.scalar(
        select(TenantBackupConnection).where(
            TenantBackupConnection.tenant_id == tenant_id,
            TenantBackupConnection.disconnected_at.is_(None),
        )
    )


def authorization_url(tenant_id: UUID, user_id: UUID, settings: Settings | None = None) -> str:
    """Signed, short-lived state binds the callback to this tenant and owner."""
    active = settings or get_settings()
    now = _now()
    state = jwt.encode(
        {
            "tenant_id": str(tenant_id),
            "sub": str(user_id),
            "aud": STATE_AUDIENCE,
            "iss": active.jwt_issuer,
            "iat": now,
            "exp": now + STATE_TTL,
            "jti": str(uuid4()),
        },
        active.jwt_secret,
        algorithm="HS256",
    )
    return oauth_client(active).authorization_url(state)


def _read_state(state: str, tenant_id: UUID, user_id: UUID, settings: Settings) -> None:
    try:
        claims = jwt.decode(
            state,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=STATE_AUDIENCE,
            issuer=settings.jwt_issuer,
            options={"require": ["tenant_id", "sub", "exp", "jti"]},
        )
    except jwt.InvalidTokenError as exc:
        raise AppError(
            400, "BACKUP_OAUTH_STATE", "The Google authorization state is not valid"
        ) from exc
    if claims["tenant_id"] != str(tenant_id) or claims["sub"] != str(user_id):
        raise AppError(400, "BACKUP_OAUTH_STATE", "The Google authorization state is not valid")


def connect(
    db: Session,
    tenant: Tenant,
    user_id: UUID,
    code: str,
    state: str,
    settings: Settings | None = None,
) -> TenantBackupConnection:
    """Exchange the OAuth code, create the tenant folder and store the wrapped refresh token."""
    active = settings or get_settings()
    _read_state(state, tenant.id, user_id, active)
    master = backup_crypto.load_master_key(active.backup_master_key)
    grant = oauth_client(active).exchange_code(code)
    folder_id = drive_client(active, grant.refresh_token).ensure_folder(folder_name(tenant))
    existing = active_connection(db, tenant.id)
    if existing is not None:
        existing.disconnected_at = _now()
    connection = TenantBackupConnection(
        tenant_id=tenant.id,
        provider="google_drive",
        account_email=grant.account_email,
        folder_id=folder_id,
        folder_name=folder_name(tenant),
        scopes=grant.scopes,
        wrapped_refresh_token=backup_crypto.wrap_secret(
            master, grant.refresh_token, tenant.id, "drive-refresh"
        ),
        kek_id=active.backup_kek_id,
        connected_by_user_id=user_id,
        connected_at=_now(),
    )
    db.add(connection)
    db.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor_user_id=user_id,
            action="BACKUP_CONNECTED",
            entity_type="tenant_backup_connection",
            entity_id=connection.id,
            details={"provider": "google_drive", "folder": folder_name(tenant)},
        )
    )
    db.commit()
    set_tenant_scope(db, tenant.id)
    return connection


def disconnect(db: Session, tenant_id: UUID, user_id: UUID) -> None:
    """Forget the refresh token. Encrypted files stay in the owner's Drive (owner deletes)."""
    connection = active_connection(db, tenant_id)
    if connection is None:
        raise AppError(404, "BACKUP_NOT_CONNECTED", "No Google Drive backup is connected")
    connection.disconnected_at = _now()
    connection.wrapped_refresh_token = b""
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="BACKUP_DISCONNECTED",
            entity_type="tenant_backup_connection",
            entity_id=connection.id,
            details={},
        )
    )
    db.commit()
    set_tenant_scope(db, tenant_id)


def _drive(
    db: Session, tenant_id: UUID, settings: Settings
) -> tuple[TenantBackupConnection, DriveClient]:
    connection = active_connection(db, tenant_id)
    if connection is None:
        raise AppError(409, "BACKUP_NOT_CONNECTED", "Connect Google Drive before running a backup")
    master = backup_crypto.load_master_key(settings.backup_master_key)
    token = backup_crypto.unwrap_secret(
        master, connection.wrapped_refresh_token, tenant_id, "drive-refresh"
    )
    return connection, drive_client(settings, token)


# ---------------------------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------------------------


def _current_key(db: Session, tenant_id: UUID, settings: Settings) -> tuple[TenantBackupKey, bytes]:
    master = backup_crypto.load_master_key(settings.backup_master_key)
    record = db.scalar(
        select(TenantBackupKey)
        .where(TenantBackupKey.tenant_id == tenant_id, TenantBackupKey.retired_at.is_(None))
        .order_by(TenantBackupKey.created_at.desc())
    )
    if record is None:
        data_key = backup_crypto.generate_key()
        record = TenantBackupKey(id=uuid4(), tenant_id=tenant_id, kek_id=settings.backup_kek_id)
        record.wrapped_key = backup_crypto.wrap_key(master, data_key, tenant_id, record.id)
        db.add(record)
        db.flush()
        return record, data_key
    return record, backup_crypto.unwrap_key(master, record.wrapped_key, tenant_id, record.id)


def rotate_master_key(db: Session, old_key: str, new_key: str, new_kek_id: str) -> int:
    """Re-wrap every tenant key and refresh token under a new master key (runbook step)."""
    old = backup_crypto.load_master_key(old_key)
    new = backup_crypto.load_master_key(new_key)
    count = 0
    for key in db.scalars(select(TenantBackupKey)):
        plain = backup_crypto.unwrap_key(old, key.wrapped_key, key.tenant_id, key.id)
        key.wrapped_key = backup_crypto.wrap_key(new, plain, key.tenant_id, key.id)
        key.kek_id = new_kek_id
        count += 1
    for connection in db.scalars(
        select(TenantBackupConnection).where(TenantBackupConnection.disconnected_at.is_(None))
    ):
        token = backup_crypto.unwrap_secret(
            old, connection.wrapped_refresh_token, connection.tenant_id, "drive-refresh"
        )
        connection.wrapped_refresh_token = backup_crypto.wrap_secret(
            new, token, connection.tenant_id, "drive-refresh"
        )
        connection.kek_id = new_kek_id
        count += 1
    db.commit()
    return count


# ---------------------------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------------------------


def _manifest_core(
    backup: TenantBackup, key: TenantBackupKey, counts: dict[str, int], migration: Any
) -> dict[str, Any]:
    return {
        "schema_version": backup_export.SCHEMA_VERSION,
        "backup_id": str(backup.id),
        "tenant_id": str(backup.tenant_id),
        "created_at": backup.created_at.isoformat(),
        "app_version": APP_VERSION,
        "migration_version": migration,
        "encryption": {
            "algorithm": "AES-256-GCM",
            "format_version": backup_crypto.FORMAT_VERSION,
            "key_id": str(key.id),
            "kek_id": key.kek_id,
        },
        "counts": counts,
    }


def run_backup(
    db: Session,
    tenant_id: UUID,
    actor_id: UUID | None,
    kind: str = "MANUAL",
    settings: Settings | None = None,
    now: datetime | None = None,
) -> TenantBackup:
    active = settings or get_settings()
    connection, drive = _drive(db, tenant_id, active)
    backup = TenantBackup(
        id=uuid4(),
        tenant_id=tenant_id,
        kind=kind,
        status="RUNNING",
        requested_by_user_id=actor_id,
        created_at=now or _now(),
        manifest={},
    )
    db.add(backup)
    db.flush()
    try:
        key, data_key = _current_key(db, tenant_id, active)
        document, counts = backup_export.export_tenant(db, tenant_id)
        core = _manifest_core(backup, key, counts, document["migration_version"])
        blob = backup_crypto.encrypt_payload(data_key, backup_export.serialize(document), core)
        digest = backup_crypto.checksum(blob)
        stamp = backup.created_at.strftime("%Y%m%dT%H%M%SZ")
        name = f"tawzeevo-{tenant_id}-{stamp}-{kind.lower()}.tzb"
        remote = drive.upload(connection.folder_id, name, blob)
        backup.key_id = key.id
        backup.file_name = name
        backup.remote_file_id = remote.id
        backup.byte_size = len(blob)
        backup.checksum = digest
        backup.manifest = {**core, "checksum": digest, "byte_size": len(blob), "file_name": name}
        backup.status = "UPLOADED"
        backup.completed_at = _now()
        connection.last_error = None
    except AppError as error:
        backup.status = "FAILED"
        backup.error = f"{error.code}: {error.message}"[:400]
        connection.last_error = backup.error
        db.commit()
        set_tenant_scope(db, tenant_id)
        raise
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_id,
            action="BACKUP_UPLOADED",
            entity_type="tenant_backup",
            entity_id=backup.id,
            details={"kind": kind, "checksum": digest, "byte_size": len(blob)},
        )
    )
    db.commit()
    set_tenant_scope(db, tenant_id)
    apply_retention(db, tenant_id, drive)
    return backup


def apply_retention(db: Session, tenant_id: UUID, drive: DriveClient) -> int:
    """Keep the newest 30 daily/manual and 12 monthly backups (D-056); delete the rest."""
    uploaded = list(
        db.scalars(
            select(TenantBackup)
            .where(TenantBackup.tenant_id == tenant_id, TenantBackup.status == "UPLOADED")
            .order_by(TenantBackup.created_at.desc())
        )
    )
    monthly = [b for b in uploaded if b.kind == "MONTHLY"]
    daily = [b for b in uploaded if b.kind != "MONTHLY"]
    expired = daily[DAILY_RETENTION:] + monthly[MONTHLY_RETENTION:]
    for backup in expired:
        if backup.remote_file_id:
            drive.delete(backup.remote_file_id)
        backup.status = "DELETED"
        backup.deleted_at = _now()
    if expired:
        db.commit()
        set_tenant_scope(db, tenant_id)
    return len(expired)


def _due_kind(db: Session, tenant_id: UUID, now: datetime) -> str | None:
    latest = db.scalar(
        select(TenantBackup)
        .where(TenantBackup.tenant_id == tenant_id, TenantBackup.status == "UPLOADED")
        .order_by(TenantBackup.created_at.desc())
    )
    if latest is not None and now - latest.created_at < DAILY_INTERVAL:
        return None
    first_of_month = db.scalar(
        select(TenantBackup).where(
            TenantBackup.tenant_id == tenant_id,
            TenantBackup.kind == "MONTHLY",
            TenantBackup.status == "UPLOADED",
            TenantBackup.created_at
            >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        )
    )
    return "DAILY" if first_of_month is not None else "MONTHLY"


def run_due_backups(
    db: Session, now: datetime | None = None, settings: Settings | None = None
) -> list[UUID]:
    """Scheduled entry: one backup per connected active tenant per 24 h; monthly first.

    The tenant list comes from the global `tenants` table and this tenant's RLS scope is bound
    before the connection lookup, so the job discovers the same connections under a database
    role that is subject to row-level security as under one that bypasses it. No tenant ever
    sees another tenant's rows: every read below runs inside one bound scope.
    """
    active = settings or get_settings()
    moment = now or _now()
    done: list[UUID] = []
    for tenant_id in all_tenant_ids(db):
        tenant = db.get(Tenant, tenant_id)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            continue
        set_tenant_scope(db, tenant.id)
        if active_connection(db, tenant.id) is None:
            continue
        kind = _due_kind(db, tenant.id, moment)
        if kind is None:
            continue
        try:
            run_backup(db, tenant.id, None, kind, active, moment)
            done.append(tenant.id)
            metrics.increment("backup_runs")
        except AppError as error:
            metrics.increment("backup_failures")
            logger.warning("scheduled backup failed for tenant %s: %s", tenant.id, error.code)
    return done


# ---------------------------------------------------------------------------------------------
# Restore: drill (verify) and controlled import
# ---------------------------------------------------------------------------------------------


def _get_backup(db: Session, tenant_id: UUID, backup_id: UUID) -> TenantBackup:
    backup = db.get(TenantBackup, backup_id)
    if backup is None or backup.tenant_id != tenant_id or backup.status != "UPLOADED":
        raise AppError(404, "BACKUP_NOT_FOUND", "Backup was not found")
    return backup


def _fetch_and_decrypt(
    db: Session, backup: TenantBackup, settings: Settings
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Download, verify checksum, unwrap key, authenticate/decrypt, parse and reconcile."""
    _connection, drive = _drive(db, backup.tenant_id, settings)
    assert backup.remote_file_id and backup.key_id
    blob = drive.download(backup.remote_file_id)
    if backup_crypto.checksum(blob) != backup.checksum:
        raise backup_crypto.BackupIntegrityError("Backup checksum does not match the manifest")
    key = db.get(TenantBackupKey, backup.key_id)
    if key is None:
        raise AppError(409, "BACKUP_KEY_MISSING", "The backup key record is missing")
    master = backup_crypto.load_master_key(settings.backup_master_key)
    data_key = backup_crypto.unwrap_key(master, key.wrapped_key, backup.tenant_id, key.id)
    core = {
        k: v for k, v in backup.manifest.items() if k not in {"checksum", "byte_size", "file_name"}
    }
    payload = backup_crypto.decrypt_payload(data_key, blob, core)
    document = backup_export.parse(payload)
    if document["tenant"]["id"] != str(backup.tenant_id):
        raise backup_crypto.BackupIntegrityError("Backup tenant does not match")
    counts_raw = backup.manifest.get("counts", {})
    counts = {str(k): int(v) for k, v in counts_raw.items()} if isinstance(counts_raw, dict) else {}
    report = backup_export.reconcile(document, counts)
    if not report["consistent"]:
        raise backup_crypto.BackupIntegrityError("Backup row counts do not match the manifest")
    return document, report


def verify_backup(
    db: Session,
    tenant_id: UUID,
    backup_id: UUID,
    actor_id: UUID | None,
    settings: Settings | None = None,
) -> TenantBackupRestore:
    """Restore drill: proves the backup can be decrypted and is whole, touching no live data."""
    active = settings or get_settings()
    backup = _get_backup(db, tenant_id, backup_id)
    record = TenantBackupRestore(
        tenant_id=tenant_id,
        backup_id=backup.id,
        mode="VERIFY",
        status="FAILED",
        report={},
        requested_by_user_id=actor_id,
    )
    try:
        _document, report = _fetch_and_decrypt(db, backup, active)
        record.status = "VERIFIED"
        record.report = {
            **report,
            "checksum": backup.checksum,
            "migration_version": backup.manifest.get("migration_version"),
        }
    except AppError as error:
        record.report = {"error": error.code, "message": error.message}
        db.add(record)
        db.commit()
        set_tenant_scope(db, tenant_id)
        raise
    db.add(record)
    db.commit()
    set_tenant_scope(db, tenant_id)
    return record


def import_backup(
    db: Session, tenant_id: UUID, backup_id: UUID, actor_id: UUID, settings: Settings | None = None
) -> TenantBackupRestore:
    """Controlled import (runbook step 6) into an EMPTY tenant; platform administrators only."""
    active = settings or get_settings()
    backup = _get_backup(db, tenant_id, backup_id)
    record = TenantBackupRestore(
        tenant_id=tenant_id,
        backup_id=backup.id,
        mode="IMPORT",
        status="FAILED",
        report={},
        requested_by_user_id=actor_id,
    )
    try:
        document, report = _fetch_and_decrypt(db, backup, active)
        imported = backup_export.import_tenant(db, tenant_id, document)
        tenant = db.get(Tenant, tenant_id)
        if tenant is not None:
            # Devices synced against the lost data must re-bootstrap (410) instead of merging.
            tenant.sync_retention_floor = max(
                tenant.sync_retention_floor, high_water(db, tenant_id)
            )
        record.status = "IMPORTED"
        record.report = {**report, "imported": imported}
        db.add(record)
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor_id,
                action="BACKUP_IMPORTED",
                entity_type="tenant_backup",
                entity_id=backup.id,
                details={"rows": report["rows"]},
            )
        )
        db.commit()
    except AppError as error:
        db.rollback()
        set_tenant_scope(db, tenant_id)
        record.report = {"error": error.code, "message": error.message}
        db.add(record)
        db.commit()
        set_tenant_scope(db, tenant_id)
        raise
    set_tenant_scope(db, tenant_id)
    return record


# ---------------------------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------------------------


def list_backups(db: Session, tenant_id: UUID, limit: int = 50) -> list[TenantBackup]:
    return list(
        db.scalars(
            select(TenantBackup)
            .where(TenantBackup.tenant_id == tenant_id)
            .order_by(TenantBackup.created_at.desc())
            .limit(limit)
        )
    )


def latest_restore(db: Session, tenant_id: UUID) -> TenantBackupRestore | None:
    return db.scalar(
        select(TenantBackupRestore)
        .where(TenantBackupRestore.tenant_id == tenant_id)
        .order_by(TenantBackupRestore.created_at.desc())
    )
