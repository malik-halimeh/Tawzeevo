"""Driver collection reports and customer notifications (D-114).

A driver completing a delivery says what was collected. The report is stored as PENDING with the
completion, in the same transaction and exactly once per delivery. It is not a payment (D-063 as
amended): the owner confirms it, which records a receipt through the existing receipt service,
allocated to that invoice, or rejects it with a reason."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    CollectionReport,
    Customer,
    CustomerLedgerEntry,
    CustomerNotification,
    DeliveryTask,
    Invoice,
    TenantMembership,
    User,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.collection_reports import (
    CollectionClaim,
    CollectionReportResponse,
    CustomerNotificationListResponse,
    CustomerNotificationResponse,
)
from tawzeevo_api.schemas.payments import AllocationSelectionRequest, CustomerReceiptRequest
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.payments import record_customer_receipt

RECEIPT_KEY_NAMESPACE = UUID("2d8f6a1c-5b3e-4f09-a7c4-9e1b0d2f6a14")
NOTIFICATION_LIMIT = 30


def create_report_row(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    task: DeliveryTask,
    currency: str,
    outstanding: Decimal,
    claim: CollectionClaim,
    idempotency_key: UUID | None,
) -> CollectionReport | None:
    """No commit: runs inside the completion's transaction (API and offline push alike)."""
    if outstanding <= 0:
        return None  # nothing was owed on this delivery: nothing to report
    if claim.kind == "FULL":
        amount: Decimal | None = money(outstanding)
    elif claim.kind == "PARTIAL":
        assert claim.amount is not None
        amount = money(claim.amount)
        if amount > outstanding:
            raise AppError(
                422,
                "COLLECTION_AMOUNT_TOO_HIGH",
                "The amount paid is more than what is owed on this delivery",
            )
    else:
        amount = None
    report = CollectionReport(
        id=uuid4(),
        tenant_id=tenant_id,
        task_id=task.id,
        invoice_id=task.invoice_id,
        customer_id=task.customer_id,
        reporter_membership_id=membership.id,
        kind=claim.kind,
        amount=amount,
        currency=currency,
        status="PENDING",
        idempotency_key=idempotency_key or claim.idempotency_key or uuid4(),
    )
    db.add(report)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=membership.user_id,
            action="COLLECTION_REPORTED",
            entity_type="collection_report",
            entity_id=report.id,
            details={"task_id": str(task.id), "kind": claim.kind, "amount": str(amount or "")},
        )
    )
    return report


def list_reports(db: Session, tenant_id: UUID, status: str | None) -> list[CollectionReport]:
    set_tenant_scope(db, tenant_id)
    query = select(CollectionReport).where(CollectionReport.tenant_id == tenant_id)
    if status:
        query = query.where(CollectionReport.status == status)
    return list(db.scalars(query.order_by(CollectionReport.created_at.desc()).limit(200)))


def _get(db: Session, tenant_id: UUID, report_id: UUID) -> CollectionReport:
    set_tenant_scope(db, tenant_id)
    report = db.scalar(
        select(CollectionReport)
        .where(CollectionReport.tenant_id == tenant_id, CollectionReport.id == report_id)
        .with_for_update()
    )
    if report is None:
        raise AppError(404, "COLLECTION_REPORT_NOT_FOUND", "Collection report was not found")
    return report


def _decide(report: CollectionReport, actor: UUID, status: str) -> None:
    report.status = status
    report.decided_by_user_id = actor
    report.decided_at = datetime.now(UTC)


def confirm_report(db: Session, tenant_id: UUID, actor: UUID, report_id: UUID) -> CollectionReport:
    report = _get(db, tenant_id, report_id)
    if report.status == "CONFIRMED":
        return report
    if report.status != "PENDING":
        raise AppError(409, "COLLECTION_REPORT_DECIDED", "This report was already decided")
    if report.kind == "NONE":
        # "Not paid" is acknowledged; nothing is recorded as money.
        _decide(report, actor, "CONFIRMED")
        _audit(db, tenant_id, actor, "COLLECTION_ACKNOWLEDGED", report.id, {})
        commit_and_restore_tenant_scope(db, tenant_id)
        return report
    invoice = db.get(Invoice, report.invoice_id)
    charge = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.source_effect_key == f"invoice:{report.invoice_id}:charge",
        )
    )
    if invoice is None or charge is None:
        raise AppError(409, "INVOICE_NOT_CHARGEABLE", "The invoice has no open charge to pay")
    assert report.amount is not None
    amount = report.amount
    reporter = db.get(TenantMembership, report.reporter_membership_id)
    user = db.get(User, reporter.user_id) if reporter else None
    payment = record_customer_receipt(
        db,
        tenant_id,
        actor,
        CustomerReceiptRequest(
            idempotency_key=uuid5(RECEIPT_KEY_NAMESPACE, f"collection-report:{report.id}"),
            customer_id=report.customer_id,
            amount=report.amount,
            currency=report.currency,
            method="CASH",
            reference=invoice.official_invoice_number,
            paid_at=report.created_at,
            notes=f"Collected on delivery by {user.first_name} {user.last_name}".strip()
            if user
            else "Collected on delivery",
            allocations=[
                AllocationSelectionRequest(target_ledger_entry_id=charge.id, amount=report.amount)
            ],
        ),
    )
    report = _get(db, tenant_id, report_id)
    if report.status == "PENDING":
        _decide(report, actor, "CONFIRMED")
        report.confirmed_payment_id = payment.id
        _audit(
            db, tenant_id, actor, "COLLECTION_CONFIRMED", report.id, {"payment_id": str(payment.id)}
        )
        db.add(
            CustomerNotification(
                tenant_id=tenant_id,
                customer_id=report.customer_id,
                kind="PAYMENT_RECORDED",
                data={
                    "amount": f"{money(amount):f}",
                    "currency": report.currency,
                    "invoice_number": invoice.official_invoice_number or "",
                },
            )
        )
        commit_and_restore_tenant_scope(db, tenant_id)
    return report


def reject_report(
    db: Session, tenant_id: UUID, actor: UUID, report_id: UUID, reason: str
) -> CollectionReport:
    report = _get(db, tenant_id, report_id)
    if report.status != "PENDING":
        raise AppError(409, "COLLECTION_REPORT_DECIDED", "This report was already decided")
    _decide(report, actor, "REJECTED")
    report.reason = reason.strip()
    _audit(db, tenant_id, actor, "COLLECTION_REJECTED", report.id, {"reason": report.reason})
    commit_and_restore_tenant_scope(db, tenant_id)
    return report


def _audit(
    db: Session, tenant_id: UUID, actor: UUID, action: str, report_id: UUID, details: dict[str, str]
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action=action,
            entity_type="collection_report",
            entity_id=report_id,
            details=details,
        )
    )


def report_response(db: Session, report: CollectionReport) -> CollectionReportResponse:
    invoice = db.get(Invoice, report.invoice_id)
    customer = db.get(Customer, report.customer_id)
    membership = db.get(TenantMembership, report.reporter_membership_id)
    user = db.get(User, membership.user_id) if membership else None
    return CollectionReportResponse(
        id=report.id,
        status=report.status,
        kind=report.kind,
        amount=money(report.amount) if report.amount is not None else None,
        currency=report.currency,
        task_id=report.task_id,
        invoice_id=report.invoice_id,
        official_invoice_number=invoice.official_invoice_number if invoice else None,
        customer_id=report.customer_id,
        customer_name=customer.name if customer else "",
        reporter_name=f"{user.first_name} {user.last_name}".strip() if user else "",
        confirmed_payment_id=report.confirmed_payment_id,
        reason=report.reason,
        created_at=report.created_at,
        decided_at=report.decided_at,
    )


# ---------- customer notifications (reached only through the customer-access rules) ----------


def customer_notifications(
    db: Session, tenant_id: UUID, customer_id: UUID
) -> CustomerNotificationListResponse:
    set_tenant_scope(db, tenant_id)
    scope = (
        CustomerNotification.tenant_id == tenant_id,
        CustomerNotification.customer_id == customer_id,
    )
    unread = int(
        db.scalar(
            select(func.count())
            .select_from(CustomerNotification)
            .where(*scope, CustomerNotification.read_at.is_(None))
        )
        or 0
    )
    rows = db.scalars(
        select(CustomerNotification)
        .where(*scope)
        .order_by(CustomerNotification.created_at.desc(), CustomerNotification.id.desc())
        .limit(NOTIFICATION_LIMIT)
    )
    return CustomerNotificationListResponse(
        unread=unread,
        notifications=[
            CustomerNotificationResponse(
                id=row.id,
                kind=row.kind,
                data={key: str(value) for key, value in row.data.items()},
                created_at=row.created_at,
                read=row.read_at is not None,
            )
            for row in rows
        ],
    )


def mark_notifications_read(db: Session, tenant_id: UUID, customer_id: UUID) -> None:
    set_tenant_scope(db, tenant_id)
    db.execute(
        update(CustomerNotification)
        .where(
            CustomerNotification.tenant_id == tenant_id,
            CustomerNotification.customer_id == customer_id,
            CustomerNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    commit_and_restore_tenant_scope(db, tenant_id)
