"""Change-log recording for offline synchronization (PHASE_04.md F).

Every tracked tenant-owned row that is inserted, updated or deleted produces one `sync_changes`
record inside the same flush, so the domain mutation and its change record commit atomically.
Mutable, conflict-sensitive rows (customers, categories, tenant products) also receive a monotonic
`version` bump here. Immutable financial rows only ever produce insert changes.

Projections are deliberately small and explicit: they are what a device stores locally, never an
owner API response object. Nothing here reads cost, profit or supplier pricing into a projection
that a driver device could later receive (Phase 7 narrows projections per role).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    Category,
    Customer,
    CustomerLedgerEntry,
    DeliveryTask,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    Payment,
    ProcurementItem,
    SyncChange,
    TenantBarcode,
    TenantProduct,
    TenantProductCostEntry,
    TenantSupplier,
)

PROTOCOL_VERSION = 1
# Highest local (IndexedDB) schema the server knows how to serve; the PWA declares its own.
APP_SCHEMA_VERSION = 2

VERSIONED_TYPES: tuple[type, ...] = (Customer, Category, TenantProduct, TenantSupplier)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return str(value.value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def _fields(row: object, names: tuple[str, ...]) -> dict[str, Any]:
    return {name: _plain(getattr(row, name)) for name in names}


def _customer(row: Customer) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "name",
            "phone",
            "phone_raw",
            "address",
            "latitude",
            "longitude",
            "grade",
            "version",
            "created_at",
            "updated_at",
        ),
    )


def _category(row: Category) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "master_category_id",
            "name_en",
            "name_ar",
            "slug",
            "display_order",
            "is_active",
            "archived_at",
            "version",
            "created_at",
            "updated_at",
        ),
    )


def _product(row: TenantProduct) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "category_id",
            "master_product_id",
            "name",
            "is_published",
            "unit_price",
            "currency",
            "price_basis",
            "pieces_per_box",
            "version",
            "created_at",
            "updated_at",
        ),
    )


def _barcode(row: TenantBarcode) -> dict[str, Any]:
    return _fields(
        row, ("id", "tenant_id", "tenant_product_id", "barcode", "package_level", "created_at")
    )


def _invoice(row: Invoice) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "customer_id",
            "status",
            "official_invoice_number",
            "current_revision_id",
            "confirmed_revision_id",
            "confirmed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ),
    )


def _revision(row: InvoiceRevision) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "invoice_id",
            "client_command_id",
            "predecessor_revision_id",
            "server_revision_number",
            "currency",
            "customer_id",
            "customer_snapshot",
            "prior_balance_snapshot",
            "subtotal",
            "discount_total",
            "markup_total",
            "net_sales",
            "amount_due_display",
            "created_at",
        ),
    )


def _revision_item(row: InvoiceRevisionItem) -> dict[str, Any]:
    # Owner projection: price fields only. Cost/profit fields are intentionally excluded so the
    # same projection can later serve a driver device without leaking supplier costs (D-031).
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "invoice_revision_id",
            "line_number",
            "tenant_product_id",
            "product_name",
            "barcode",
            "quantity",
            "price_basis",
            "pieces_per_box",
            "normal_unit_price",
            "effective_unit_price",
            "line_discount",
            "line_markup",
            "line_total",
        ),
    )


def _payment(row: Payment) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "customer_id",
            "supplier_id",
            "direction",
            "currency",
            "amount",
            "paid_at",
            "method",
            "reference",
            "reverses_payment_id",
            "idempotency_key",
        ),
    )


def _ledger_entry(row: CustomerLedgerEntry) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "customer_id",
            "currency",
            "signed_amount",
            "entry_type",
            "source_type",
            "source_id",
            "effective_at",
            "reverses_entry_id",
        ),
    )


def _supplier(row: TenantSupplier) -> dict[str, Any]:
    # Identity, contact and location only — never costs (PHASE_06.md B/F).
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "name",
            "contact_name",
            "contact_phone",
            "contact_phone_raw",
            "address",
            "latitude",
            "longitude",
            "notes",
            "version",
            "created_at",
            "updated_at",
        ),
    )


def _product_cost(row: TenantProductCostEntry) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "tenant_product_id",
            "supplier_id",
            "unit_cost",
            "currency",
            "cost_basis",
            "pieces_per_box",
            "effective_at",
            "source_type",
            "quantity_context",
            "notes",
            "created_at",
        ),
    )


def _procurement_item(row: ProcurementItem) -> dict[str, Any]:
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "list_id",
            "tenant_product_id",
            "product_name",
            "supplier_id",
            "price_basis",
            "pieces_per_box",
            "origin",
            "required_quantity",
            "target_quantity",
            "purchased_quantity",
            "notes",
            "version",
            "updated_at",
        ),
    )


def _delivery_task(row: DeliveryTask) -> dict[str, Any]:
    # The feed carries the task row only; the member-facing projection is built by the API.
    return _fields(
        row,
        (
            "id",
            "tenant_id",
            "invoice_id",
            "customer_id",
            "assigned_membership_id",
            "status",
            "delivery_date",
            "route_sequence",
            "currency",
            "amount_to_collect",
            "notes",
            "version",
            "updated_at",
        ),
    )


PROJECTIONS: dict[type, tuple[str, Callable[[Any], dict[str, Any]]]] = {
    Customer: ("customer", _customer),
    TenantSupplier: ("supplier", _supplier),
    DeliveryTask: ("delivery_task", _delivery_task),
    Category: ("category", _category),
    TenantProduct: ("tenant_product", _product),
    TenantBarcode: ("tenant_barcode", _barcode),
    Invoice: ("invoice", _invoice),
    InvoiceRevision: ("invoice_revision", _revision),
    InvoiceRevisionItem: ("invoice_revision_item", _revision_item),
    Payment: ("payment", _payment),
    CustomerLedgerEntry: ("customer_ledger_entry", _ledger_entry),
}

# Push-result projections that are not part of the change feed (append-only rows the device
# does not mirror, and procurement lines whose full read lives in the owner API).
RESULT_PROJECTIONS: dict[type, Callable[[Any], dict[str, Any]]] = {
    TenantProductCostEntry: _product_cost,
    ProcurementItem: _procurement_item,
}

# Set by the push service for the duration of one operation so change rows carry its identity.
_operation_context: dict[int, tuple[UUID, UUID]] = {}


def set_operation_context(
    session: Session, operation_id: UUID | None, device_installation_id: UUID | None
) -> None:
    key = id(session)
    if operation_id is None or device_installation_id is None:
        _operation_context.pop(key, None)
    else:
        _operation_context[key] = (operation_id, device_installation_id)


def _record(session: Session, row: object, operation: str) -> None:
    entry = PROJECTIONS.get(type(row))
    if entry is None:
        return
    entity_type, project = entry
    if getattr(row, "id", None) is None:
        row.id = uuid4()  # type: ignore[attr-defined]
    context = _operation_context.get(id(session))
    session.add(
        SyncChange(
            tenant_id=row.tenant_id,  # type: ignore[attr-defined]
            entity_type=entity_type,
            entity_id=row.id,  # type: ignore[attr-defined]
            operation=operation,
            version=int(getattr(row, "version", 1) or 1),
            payload=project(row) if operation == "upsert" else {"id": str(row.id)},  # type: ignore[attr-defined]
            operation_id=context[0] if context else None,
            device_installation_id=context[1] if context else None,
        )
    )


def _before_flush(session: Session, _flush_context: object, _instances: object) -> None:
    for row in list(session.new):
        if isinstance(row, SyncChange):
            continue
        _record(session, row, "upsert")
    for row in list(session.dirty):
        if isinstance(row, SyncChange) or not session.is_modified(row, include_collections=False):
            continue
        if isinstance(row, VERSIONED_TYPES):
            state = inspect(row)
            already_bumped = bool(state is not None and state.attrs.version.history.added)
            if not already_bumped:  # not already bumped explicitly in this flush
                row.version = int(row.version or 1) + 1  # type: ignore[attr-defined]
        _record(session, row, "upsert")
    for row in list(session.deleted):
        if isinstance(row, SyncChange):
            continue
        _record(session, row, "delete")


def register_change_tracking() -> None:
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
