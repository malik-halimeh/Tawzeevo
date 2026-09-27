"""Pickup reports (D-106): the runner reports what was picked up; the owner confirms (one purchase
through the existing purchase service, with its idempotency) or rejects with a reason."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    PickupReport,
    ProcurementItem,
    ProcurementList,
    TenantMembership,
    TenantRole,
    TenantSupplier,
    User,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.pickup_reports import (
    PickupReportCreateRequest,
    PickupReportLine,
    PickupReportResponse,
)
from tawzeevo_api.schemas.supplier_purchases import PurchaseCreateRequest, PurchaseLineRequest
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.supplier_purchases import record_purchase

# Namespace for the purchase key of a confirmed report: a retried confirmation replays the purchase.
PURCHASE_KEY_NAMESPACE = UUID("6f1d3c52-8a0e-4f7b-9d61-2b7c4e0a9f13")


def _fingerprint(request: PickupReportCreateRequest) -> list[tuple[str, str, str]]:
    return [
        (str(line.procurement_item_id), f"{money(line.quantity):f}", f"{money(line.unit_cost):f}")
        for line in request.lines
    ]


def _stored_fingerprint(report: PickupReport) -> list[tuple[str, str, str]]:
    return [
        (
            line["procurement_item_id"],
            f"{money(Decimal(line['quantity'])):f}",
            f"{money(Decimal(line['unit_cost'])):f}",
        )
        for line in report.lines
    ]


def create_report(
    db: Session, tenant_id: UUID, membership: TenantMembership, request: PickupReportCreateRequest
) -> tuple[PickupReport, bool]:
    set_tenant_scope(db, tenant_id)
    existing = db.scalar(
        select(PickupReport).where(
            PickupReport.tenant_id == tenant_id,
            PickupReport.idempotency_key == request.idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.reporter_membership_id != membership.id
            or existing.procurement_list_id != request.list_id
            or existing.supplier_id != request.supplier_id
            or existing.currency != request.currency
            or _stored_fingerprint(existing) != _fingerprint(request)
        ):
            raise AppError(409, "IDEMPOTENCY_CONFLICT", "Key was already used for another report")
        return existing, True
    procurement_list = db.get(ProcurementList, request.list_id)
    if procurement_list is None or procurement_list.tenant_id != tenant_id:
        raise AppError(404, "PROCUREMENT_LIST_NOT_FOUND", "Procurement list was not found")
    if (
        membership.role is not TenantRole.OWNER
        and procurement_list.assignee_membership_id != membership.id
    ):
        raise AppError(403, "PROCUREMENT_LIST_NOT_ASSIGNED", "This list is not assigned to you")
    if procurement_list.status in ("COMPLETE", "CANCELLED"):
        raise AppError(409, "PROCUREMENT_LIST_CLOSED", "That list is complete or cancelled")
    supplier = db.get(TenantSupplier, request.supplier_id)
    if supplier is None or supplier.tenant_id != tenant_id:
        raise AppError(404, "SUPPLIER_NOT_FOUND", "Supplier was not found")
    lines: list[dict[str, str]] = []
    seen: set[UUID] = set()
    for line in request.lines:
        item = db.get(ProcurementItem, line.procurement_item_id)
        if (
            item is None
            or item.tenant_id != tenant_id
            or item.list_id != procurement_list.id
            or item.supplier_id != supplier.id
            or item.removed_at is not None
            or line.procurement_item_id in seen
        ):
            raise AppError(
                422, "PICKUP_LINE_INVALID", "A line does not belong to this list and supplier"
            )
        seen.add(line.procurement_item_id)
        lines.append(
            {
                "procurement_item_id": str(item.id),
                "product_id": str(item.tenant_product_id),
                "quantity": f"{money(line.quantity):f}",
                "unit_cost": f"{money(line.unit_cost):f}",
            }
        )
    report = PickupReport(
        tenant_id=tenant_id,
        procurement_list_id=procurement_list.id,
        supplier_id=supplier.id,
        reporter_membership_id=membership.id,
        status="PENDING",
        currency=request.currency,
        lines=lines,
        notes=request.notes,
        idempotency_key=request.idempotency_key,
    )
    db.add(report)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=membership.user_id,
            action="PICKUP_REPORTED",
            entity_type="pickup_report",
            entity_id=report.id,
            details={"list_id": str(procurement_list.id), "supplier_id": str(supplier.id)},
        )
    )
    try:
        commit_and_restore_tenant_scope(db, tenant_id)
    except IntegrityError:
        db.rollback()
        set_tenant_scope(db, tenant_id)
        again = db.scalar(
            select(PickupReport).where(
                PickupReport.tenant_id == tenant_id,
                PickupReport.idempotency_key == request.idempotency_key,
            )
        )
        if again is None:
            raise
        return again, True
    return report, False


def _item_ids(report: PickupReport) -> list[UUID]:
    return [UUID(line["procurement_item_id"]) for line in report.lines]


def _get(db: Session, tenant_id: UUID, report_id: UUID, *, lock: bool = False) -> PickupReport:
    set_tenant_scope(db, tenant_id)
    query = select(PickupReport).where(
        PickupReport.tenant_id == tenant_id, PickupReport.id == report_id
    )
    report = db.scalar(query.with_for_update() if lock else query)
    if report is None:
        raise AppError(404, "PICKUP_REPORT_NOT_FOUND", "Pickup report was not found")
    return report


def list_reports(db: Session, tenant_id: UUID, status: str | None) -> list[PickupReport]:
    set_tenant_scope(db, tenant_id)
    query = select(PickupReport).where(PickupReport.tenant_id == tenant_id)
    if status:
        query = query.where(PickupReport.status == status)
    return list(db.scalars(query.order_by(PickupReport.created_at.desc()).limit(200)))


def confirm_report(db: Session, tenant_id: UUID, actor: UUID, report_id: UUID) -> PickupReport:
    """One purchase for the report through the existing purchase service; a repeated confirmation
    returns the same report (the purchase key is derived from the report)."""
    report = _get(db, tenant_id, report_id, lock=True)
    if report.status == "CONFIRMED":
        return report
    if report.status != "PENDING":
        raise AppError(409, "PICKUP_REPORT_DECIDED", "This report was already decided")
    items = {
        item.id: item
        for item in db.scalars(
            select(ProcurementItem).where(
                ProcurementItem.tenant_id == tenant_id,
                ProcurementItem.id.in_(
                    [UUID(line["procurement_item_id"]) for line in report.lines]
                ),
            )
        )
    }
    purchase_lines = []
    for line in report.lines:
        item = items[UUID(line["procurement_item_id"])]
        purchase_lines.append(
            PurchaseLineRequest(
                product_id=UUID(line["product_id"]),
                quantity=Decimal(line["quantity"]),
                unit_cost=Decimal(line["unit_cost"]),
                price_basis=item.price_basis,
                pieces_per_box=item.pieces_per_box,
                procurement_item_id=item.id,
            )
        )
    purchase, _replayed = record_purchase(
        db,
        tenant_id,
        actor,
        PurchaseCreateRequest(
            idempotency_key=uuid5(PURCHASE_KEY_NAMESPACE, f"pickup-report:{report.id}"),
            supplier_id=report.supplier_id,
            currency=report.currency,
            procurement_list_id=report.procurement_list_id,
            notes=report.notes,
            items=purchase_lines,
        ),
    )
    report = _get(db, tenant_id, report_id, lock=True)
    if report.status == "PENDING":
        report.status = "CONFIRMED"
        report.confirmed_purchase_id = purchase.id
        report.decided_by_user_id = actor
        report.decided_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor,
                action="PICKUP_CONFIRMED",
                entity_type="pickup_report",
                entity_id=report.id,
                details={"purchase_id": str(purchase.id)},
            )
        )
        commit_and_restore_tenant_scope(db, tenant_id)
    return report


def reject_report(
    db: Session, tenant_id: UUID, actor: UUID, report_id: UUID, reason: str
) -> PickupReport:
    report = _get(db, tenant_id, report_id, lock=True)
    if report.status != "PENDING":
        raise AppError(409, "PICKUP_REPORT_DECIDED", "This report was already decided")
    report.status = "REJECTED"
    report.reason = reason.strip()
    report.decided_by_user_id = actor
    report.decided_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="PICKUP_REJECTED",
            entity_type="pickup_report",
            entity_id=report.id,
            details={"reason": report.reason},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return report


def report_response(db: Session, tenant_id: UUID, report: PickupReport) -> PickupReportResponse:
    procurement_list = db.get(ProcurementList, report.procurement_list_id)
    supplier = db.get(TenantSupplier, report.supplier_id)
    membership = db.get(TenantMembership, report.reporter_membership_id)
    user = db.get(User, membership.user_id) if membership else None
    names = {
        item.id: item.product_name
        for item in db.scalars(
            select(ProcurementItem).where(
                ProcurementItem.tenant_id == tenant_id,
                ProcurementItem.id.in_(
                    [UUID(line["procurement_item_id"]) for line in report.lines]
                ),
            )
        )
    }
    lines = [
        PickupReportLine(
            procurement_item_id=UUID(line["procurement_item_id"]),
            product_id=UUID(line["product_id"]),
            product_name=names.get(UUID(line["procurement_item_id"]), ""),
            quantity=Decimal(line["quantity"]),
            unit_cost=Decimal(line["unit_cost"]),
        )
        for line in report.lines
    ]
    total = sum((line.quantity * line.unit_cost for line in lines), Decimal("0"))
    return PickupReportResponse(
        id=report.id,
        status=report.status,
        list_id=report.procurement_list_id,
        list_title=procurement_list.title if procurement_list else "",
        supplier_id=report.supplier_id,
        supplier_name=supplier.name if supplier else "",
        reporter_name=f"{user.first_name} {user.last_name}".strip() if user else "",
        currency=report.currency,
        total=money(total),
        notes=report.notes,
        lines=lines,
        confirmed_purchase_id=report.confirmed_purchase_id,
        reason=report.reason,
        created_at=report.created_at,
        decided_at=report.decided_at,
    )
