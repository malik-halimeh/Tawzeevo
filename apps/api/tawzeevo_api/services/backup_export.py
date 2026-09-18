"""Tenant data export and controlled import for encrypted backups (PHASE_04.md L).

The export is a plain, versioned JSON document of every tenant-owned business row. The import is
the last step of the restore runbook: it only ever fills an EMPTY tenant (ids preserved, so a
lost tenant is re-created under its original id in the recovery environment) and never overwrites
a live tenant. Platform users and memberships are platform data, restored separately.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from tawzeevo_api.database import Base
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    Category,
    Customer,
    CustomerLedgerEntry,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceSequence,
    Payment,
    PaymentAllocation,
    ProductGradePrice,
    PublicInvoiceCapability,
    SupplierLedgerEntry,
    Tenant,
    TenantBarcode,
    TenantFinancialSettings,
    TenantGradeDiscount,
    TenantProduct,
    TenantProductCostEntry,
    TenantProductImage,
    TenantSupplier,
)

SCHEMA_VERSION = 1

# Insert order respects foreign keys; the invoice/revision cycle uses deferred constraints.
EXPORTED_MODELS: tuple[type[Base], ...] = (
    TenantFinancialSettings,
    Customer,
    Category,
    TenantSupplier,
    TenantProduct,
    TenantBarcode,
    TenantGradeDiscount,
    ProductGradePrice,
    TenantProductImage,
    TenantProductCostEntry,
    InvoiceSequence,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    CustomerLedgerEntry,
    Payment,
    PaymentAllocation,
    SupplierLedgerEntry,
    PublicInvoiceCapability,
)


def _encode(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return value.hex()
    return value


def _decode(column: sa.Column[Any], value: Any) -> Any:
    if value is None:
        return None
    kind = column.type
    if isinstance(kind, PGUUID):
        return UUID(str(value))
    if isinstance(kind, sa.Numeric):
        return Decimal(str(value))
    if isinstance(kind, sa.DateTime):
        return datetime.fromisoformat(str(value))
    if isinstance(kind, sa.Date):
        return date.fromisoformat(str(value))
    if isinstance(kind, sa.LargeBinary):
        return bytes.fromhex(str(value))
    return value


def _table(model: type[Base]) -> sa.Table:
    table = model.__table__
    assert isinstance(table, sa.Table)
    return table


def _order_columns(table: sa.Table) -> list[Any]:
    keys = [name for name in ("created_at", "recorded_at", "occurred_at") if name in table.c]
    primary = [table.c[column.name] for column in table.primary_key.columns]
    return [table.c[key] for key in keys] + primary


def export_tenant(db: Session, tenant_id: UUID) -> tuple[dict[str, Any], dict[str, int]]:
    """Dump every tenant-owned business table; RLS scope must already be set by the caller."""
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise AppError(404, "TENANT_NOT_FOUND", "Tenant was not found")
    tables: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    for model in EXPORTED_MODELS:
        table = _table(model)
        rows = db.execute(
            select(table).where(table.c.tenant_id == tenant_id).order_by(*_order_columns(table))
        ).mappings()
        encoded = [{key: _encode(value) for key, value in row.items()} for row in rows]
        tables[table.name] = encoded
        counts[table.name] = len(encoded)
    migration = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    document = {
        "schema_version": SCHEMA_VERSION,
        "tenant": {"id": str(tenant.id), "name": tenant.name, "status": tenant.status.value},
        "migration_version": migration,
        "tables": tables,
    }
    return document, counts


def serialize(document: dict[str, Any]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse(payload: bytes) -> dict[str, Any]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AppError(409, "BACKUP_INTEGRITY_FAILED", "Backup payload is not readable") from exc
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise AppError(409, "BACKUP_SCHEMA_UNSUPPORTED", "Backup schema version is not supported")
    return document


def reconcile(document: dict[str, Any], manifest_counts: dict[str, int]) -> dict[str, Any]:
    """Compare the decrypted rows with the manifest counts; every difference is reported."""
    tables = document.get("tables", {})
    differences = {
        name: {"manifest": expected, "payload": len(tables.get(name, []))}
        for name, expected in manifest_counts.items()
        if len(tables.get(name, [])) != expected
    }
    return {
        "tables": len(tables),
        "rows": sum(len(rows) for rows in tables.values()),
        "differences": differences,
        "consistent": not differences,
    }


def tenant_row_count(db: Session, tenant_id: UUID) -> int:
    total = 0
    for model in EXPORTED_MODELS:
        table = _table(model)
        total += int(
            db.scalar(select(func.count()).select_from(table).where(table.c.tenant_id == tenant_id))
            or 0
        )
    return total


def import_tenant(db: Session, tenant_id: UUID, document: dict[str, Any]) -> dict[str, int]:
    """Fill an empty tenant from a verified backup. Caller sets scope and commits."""
    if document["tenant"]["id"] != str(tenant_id):
        raise AppError(409, "BACKUP_TENANT_MISMATCH", "Backup belongs to a different tenant")
    if tenant_row_count(db, tenant_id) != 0:
        raise AppError(
            409,
            "BACKUP_TARGET_NOT_EMPTY",
            "Restore only fills an empty tenant; live data is never overwritten",
        )
    imported: dict[str, int] = {}
    tables = document["tables"]
    for model in EXPORTED_MODELS:
        table = _table(model)
        pending = [
            {key: _decode(table.c[key], value) for key, value in row.items() if key in table.c}
            for row in tables.get(table.name, [])
        ]
        # Self-references (reversals, parent entries) are inserted after their targets.
        primary = [column.name for column in table.primary_key.columns]
        self_columns = [
            fk.parent.name
            for fk in table.foreign_keys
            if fk.column.table is table and fk.column.name in primary
        ]
        inserted: set[Any] = set()
        while pending:
            ready = [
                row
                for row in pending
                if all(row.get(col) is None or row[col] in inserted for col in self_columns)
            ]
            if not ready:
                raise AppError(
                    409, "BACKUP_INTEGRITY_FAILED", f"Unresolvable references in {table.name}"
                )
            db.execute(sa.insert(table), ready)
            inserted.update(row[primary[0]] for row in ready if len(primary) == 1)
            pending = [row for row in pending if row not in ready]
        imported[table.name] = len(tables.get(table.name, []))
    return imported
