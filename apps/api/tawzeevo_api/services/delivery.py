"""Delivery tasks and neutral assignment (PHASE_07.md A/B/C; D-063).

Eligibility: only a CONFIRMED invoice of this business, with no ASSIGNED task already. The
assignee is any *active* membership of the business — the owner themself or a driver — and a
sole owner is the default so a one-person business never sets up a driver. Reassignment is an
owner act and is audited; drivers cannot assign or reassign. Completion is allowed to the owner
or to the assigned member and records the actual performer. Both end states are terminal (D-063):
a mistaken completion is followed by a new task. Tasks never create, recalculate or cancel
invoices; the amount to collect is a projection of the invoice charge minus applied receipts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AllocationKind,
    AuditEvent,
    Customer,
    CustomerLedgerEntry,
    DeliveryTask,
    DeliveryTaskStatus,
    Invoice,
    InvoiceRevision,
    InvoiceRevisionItem,
    InvoiceStatus,
    Order,
    PaymentAllocation,
    TenantMembership,
    TenantRole,
    User,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.delivery import (
    AssigneeView,
    EligibleInvoice,
    MyWorkResponse,
    MyWorkTask,
    TaskCreateRequest,
    TaskLine,
    TaskListResponse,
    TaskResponse,
)
from tawzeevo_api.services.invoice_editor import money

TERMINAL = {DeliveryTaskStatus.COMPLETED.value, DeliveryTaskStatus.CANCELLED.value}


def _audit(
    db: Session, tenant_id: UUID, actor: UUID | None, action: str, task_id: UUID, **details: object
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action=action,
            entity_type="delivery_task",
            entity_id=task_id,
            details={key: str(value) for key, value in details.items()},
        )
    )


def eligible_members(db: Session, tenant_id: UUID) -> list[TenantMembership]:
    """Active owner or driver memberships (PHASE_07.md A). One membership, one role."""
    set_tenant_scope(db, tenant_id)
    return list(
        db.scalars(
            select(TenantMembership)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.is_active.is_(True),
                TenantMembership.role.in_([TenantRole.OWNER, TenantRole.DRIVER]),
            )
            .order_by(TenantMembership.created_at.asc())
        )
    )


def _member(db: Session, tenant_id: UUID, membership_id: UUID) -> TenantMembership:
    membership = db.get(TenantMembership, membership_id)
    if (
        membership is None
        or membership.tenant_id != tenant_id
        or not membership.is_active
        or membership.role not in (TenantRole.OWNER, TenantRole.DRIVER)
    ):
        raise AppError(404, "ASSIGNEE_NOT_FOUND", "Assignee must be an active owner or driver here")
    return membership


def get_task(db: Session, tenant_id: UUID, task_id: UUID) -> DeliveryTask:
    set_tenant_scope(db, tenant_id)
    row = db.get(DeliveryTask, task_id)
    if row is None or row.tenant_id != tenant_id:
        raise AppError(404, "DELIVERY_TASK_NOT_FOUND", "Delivery task was not found")
    return row


def _confirmed_invoice(db: Session, tenant_id: UUID, invoice_id: UUID) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.tenant_id != tenant_id:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice was not found")
    if invoice.status is not InvoiceStatus.CONFIRMED:
        raise AppError(409, "INVOICE_NOT_CONFIRMED", "Only a confirmed invoice can be delivered")
    if invoice.customer_id is None:
        raise AppError(409, "INVOICE_CUSTOMER_MISSING", "The invoice has no customer to deliver to")
    return invoice


def amount_to_collect(db: Session, tenant_id: UUID, invoice: Invoice) -> Decimal:
    """Invoice charge minus receipts applied to it (never below zero). A projection only."""
    charge = db.scalar(
        select(CustomerLedgerEntry).where(
            CustomerLedgerEntry.tenant_id == tenant_id,
            CustomerLedgerEntry.source_effect_key == f"invoice:{invoice.id}:charge",
        )
    )
    if charge is None:
        return Decimal("0.0000")
    applied = Decimal("0")
    for allocation in db.scalars(
        select(PaymentAllocation).where(
            PaymentAllocation.tenant_id == tenant_id,
            PaymentAllocation.target_ledger_entry_id == charge.id,
        )
    ):
        sign = Decimal("1") if allocation.kind == AllocationKind.APPLY else Decimal("-1")
        applied += sign * Decimal(allocation.amount)
    return max(Decimal("0"), money(Decimal(charge.signed_amount) - applied))


def create_task(
    db: Session, tenant_id: UUID, actor: UUID, request: TaskCreateRequest
) -> DeliveryTask:
    set_tenant_scope(db, tenant_id)
    invoice = _confirmed_invoice(db, tenant_id, request.invoice_id)
    open_task = db.scalar(
        select(DeliveryTask).where(
            DeliveryTask.invoice_id == invoice.id,
            DeliveryTask.status == DeliveryTaskStatus.ASSIGNED.value,
        )
    )
    if open_task is not None:
        raise AppError(
            409, "DELIVERY_TASK_EXISTS", "This invoice already has an open delivery task"
        )
    members = eligible_members(db, tenant_id)
    if request.assigned_membership_id is not None:
        assignee = _member(db, tenant_id, request.assigned_membership_id)
    elif len(members) == 1:
        assignee = members[0]  # sole owner: the default operator, no driver setup needed
    else:
        raise AppError(
            422, "ASSIGNEE_REQUIRED", "Several people can deliver here; choose who takes this one"
        )
    revision = db.get(InvoiceRevision, invoice.current_revision_id)
    order = db.scalar(select(Order).where(Order.invoice_id == invoice.id))
    delivery_date = request.delivery_date or (order.delivery_date if order else None)
    task = DeliveryTask(
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        order_id=order.id if order else None,
        customer_id=invoice.customer_id,
        assigned_membership_id=assignee.id,
        delivery_date=delivery_date,
        currency=revision.currency if revision else "USD",
        amount_to_collect=amount_to_collect(db, tenant_id, invoice),
        notes=request.notes,
        created_by_user_id=actor,
    )
    db.add(task)
    db.flush()
    _audit(
        db,
        tenant_id,
        actor,
        "delivery_task_created",
        task.id,
        invoice_id=invoice.id,
        assigned_membership_id=assignee.id,
        default=request.assigned_membership_id is None,
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_task(db, tenant_id, task.id)


def _check_version(task: DeliveryTask, expected: int) -> None:
    if task.version != expected:
        raise AppError(409, "DELIVERY_TASK_VERSION_CONFLICT", "Task was changed elsewhere; reload")


def _require_open(task: DeliveryTask) -> None:
    if task.status in TERMINAL:
        raise AppError(409, "DELIVERY_TASK_CLOSED", "A completed or cancelled task cannot change")


def assign_task(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    task_id: UUID,
    membership_id: UUID,
    expected_version: int,
) -> DeliveryTask:
    """Owner act only (PHASE_07.md A rules 5–7); audited with the previous assignee."""
    task = get_task(db, tenant_id, task_id)
    _require_open(task)
    _check_version(task, expected_version)
    assignee = _member(db, tenant_id, membership_id)
    if assignee.id != task.assigned_membership_id:
        previous = task.assigned_membership_id
        task.assigned_membership_id = assignee.id
        task.version += 1
        _audit(
            db,
            tenant_id,
            actor,
            "delivery_task_reassigned",
            task.id,
            previous=previous,
            assigned_membership_id=assignee.id,
        )
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_task(db, tenant_id, task_id)


def update_task(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    task_id: UUID,
    expected_version: int,
    delivery_date: date | None,
    notes: str | None,
    *,
    touch_date: bool,
) -> DeliveryTask:
    task = get_task(db, tenant_id, task_id)
    _require_open(task)
    _check_version(task, expected_version)
    changed: dict[str, object] = {}
    if touch_date and delivery_date != task.delivery_date:
        changed["delivery_date"] = delivery_date or ""
        task.delivery_date = delivery_date
    if notes is not None and notes != task.notes:
        changed["notes"] = notes
        task.notes = notes
    if changed:
        task.version += 1
        _audit(db, tenant_id, actor, "delivery_task_updated", task.id, **changed)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_task(db, tenant_id, task_id)


def complete_task(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    task_id: UUID,
    expected_version: int,
    note: str | None,
) -> DeliveryTask:
    """Owner or the assigned member; the performer is recorded (PHASE_07.md A rule 8)."""
    task = get_task(db, tenant_id, task_id)
    complete_task_row(db, tenant_id, membership, task, expected_version, note)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_task(db, tenant_id, task_id)


def cancel_task(
    db: Session,
    tenant_id: UUID,
    actor: UUID | None,
    task_id: UUID,
    expected_version: int | None,
    reason: str,
) -> DeliveryTask:
    task = get_task(db, tenant_id, task_id)
    _require_open(task)
    if expected_version is not None:
        _check_version(task, expected_version)
    task.status = DeliveryTaskStatus.CANCELLED.value
    task.cancelled_at = datetime.now(UTC)
    task.cancel_reason = reason
    task.version += 1
    _audit(db, tenant_id, actor, "delivery_task_cancelled", task.id, reason=reason)
    commit_and_restore_tenant_scope(db, tenant_id)
    return get_task(db, tenant_id, task_id)


def cancel_open_tasks_for_invoice(
    db: Session, tenant_id: UUID, invoice_id: UUID, reason: str
) -> None:
    """System cancellation (PHASE_07.md B): called from the invoice cancellation, no commit here."""
    for task in db.scalars(
        select(DeliveryTask).where(
            DeliveryTask.tenant_id == tenant_id,
            DeliveryTask.invoice_id == invoice_id,
            DeliveryTask.status == DeliveryTaskStatus.ASSIGNED.value,
        )
    ):
        task.status = DeliveryTaskStatus.CANCELLED.value
        task.cancelled_at = datetime.now(UTC)
        task.cancel_reason = reason
        task.version += 1
        _audit(db, tenant_id, None, "delivery_task_cancelled", task.id, reason=reason, system=True)


def list_tasks(
    db: Session,
    tenant_id: UUID,
    *,
    status: str | None = None,
    delivery_date: date | None = None,
    assigned_membership_id: UUID | None = None,
) -> list[DeliveryTask]:
    set_tenant_scope(db, tenant_id)
    query = select(DeliveryTask).where(DeliveryTask.tenant_id == tenant_id)
    if status:
        query = query.where(DeliveryTask.status == status)
    if delivery_date is not None:
        query = query.where(DeliveryTask.delivery_date == delivery_date)
    if assigned_membership_id is not None:
        query = query.where(DeliveryTask.assigned_membership_id == assigned_membership_id)
    return list(
        db.scalars(
            query.order_by(
                DeliveryTask.delivery_date.asc().nulls_last(),
                DeliveryTask.route_sequence.asc().nulls_last(),
                DeliveryTask.created_at.asc(),
            ).limit(500)
        )
    )


def eligible_invoices(db: Session, tenant_id: UUID) -> list[EligibleInvoice]:
    """CONFIRMED invoices with a customer and no open task (PHASE_07.md B)."""
    set_tenant_scope(db, tenant_id)
    open_ids = set(
        db.scalars(
            select(DeliveryTask.invoice_id).where(
                DeliveryTask.tenant_id == tenant_id,
                DeliveryTask.status == DeliveryTaskStatus.ASSIGNED.value,
            )
        )
    )
    rows = db.execute(
        select(Invoice, InvoiceRevision, Customer, Order)
        .join(InvoiceRevision, InvoiceRevision.id == Invoice.current_revision_id)
        .join(Customer, Customer.id == Invoice.customer_id)
        .outerjoin(Order, Order.invoice_id == Invoice.id)
        .where(Invoice.tenant_id == tenant_id, Invoice.status == InvoiceStatus.CONFIRMED)
        .order_by(Invoice.confirmed_at.desc())
        .limit(300)
    ).all()
    return [
        EligibleInvoice(
            invoice_id=invoice.id,
            official_invoice_number=invoice.official_invoice_number,
            customer_id=customer.id,
            customer_name=customer.name,
            currency=revision.currency,
            net_sales=revision.net_sales,
            confirmed_at=invoice.confirmed_at,
            order_id=order.id if order else None,
            delivery_date=order.delivery_date if order else None,
        )
        for invoice, revision, customer, order in rows
        if invoice.id not in open_ids
    ]


# ---------------------------------------------------------------------------------------------
# Projections
# ---------------------------------------------------------------------------------------------


def assignee_view(
    db: Session, membership_id: UUID | None, viewer_membership_id: UUID | None
) -> AssigneeView | None:
    if membership_id is None:
        return None
    membership = db.get(TenantMembership, membership_id)
    if membership is None:
        return None
    user = db.get(User, membership.user_id)
    return AssigneeView(
        membership_id=membership.id,
        role=membership.role.value,
        display_name=f"{user.first_name} {user.last_name}".strip() if user else "?",
        is_self=membership.id == viewer_membership_id,
    )


def task_lines(db: Session, tenant_id: UUID, invoice_id: UUID) -> list[TaskLine]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        return []
    rows = db.scalars(
        select(InvoiceRevisionItem)
        .where(
            InvoiceRevisionItem.tenant_id == tenant_id,
            InvoiceRevisionItem.invoice_revision_id == invoice.current_revision_id,
        )
        .order_by(InvoiceRevisionItem.line_number)
    )
    return [
        TaskLine(
            product_name=row.product_name,
            quantity=row.quantity,
            price_basis=row.price_basis,
            pieces_per_box=row.pieces_per_box,
        )
        for row in rows
    ]


def task_response(
    db: Session, tenant_id: UUID, task: DeliveryTask, viewer_membership_id: UUID | None
) -> TaskResponse:
    invoice = db.get(Invoice, task.invoice_id)
    customer = db.get(Customer, task.customer_id)
    assignee = assignee_view(db, task.assigned_membership_id, viewer_membership_id)
    assert assignee is not None
    return TaskResponse(
        id=task.id,
        status=task.status,
        invoice_id=task.invoice_id,
        official_invoice_number=invoice.official_invoice_number if invoice else None,
        order_id=task.order_id,
        customer_id=task.customer_id,
        customer_name=customer.name if customer else "?",
        customer_phone=customer.phone if customer else "",
        customer_address=customer.address if customer else None,
        customer_latitude=customer.latitude if customer else None,
        customer_longitude=customer.longitude if customer else None,
        assignee=assignee,
        delivery_date=task.delivery_date,
        route_sequence=task.route_sequence,
        currency=task.currency,
        amount_to_collect=amount_to_collect(db, tenant_id, invoice)
        if invoice and task.status == "ASSIGNED"
        else task.amount_to_collect,
        items=task_lines(db, tenant_id, task.invoice_id),
        notes=task.notes,
        completed_at=task.completed_at,
        performed_by=assignee_view(db, task.performed_by_membership_id, viewer_membership_id),
        completion_note=task.completion_note,
        cancelled_at=task.cancelled_at,
        cancel_reason=task.cancel_reason,
        version=task.version,
        created_at=task.created_at,
    )


def list_response(
    db: Session, tenant_id: UUID, tasks: list[DeliveryTask], viewer_membership_id: UUID
) -> TaskListResponse:
    members = eligible_members(db, tenant_id)
    views = [assignee_view(db, m.id, viewer_membership_id) for m in members]
    return TaskListResponse(
        tasks=[task_response(db, tenant_id, task, viewer_membership_id) for task in tasks],
        eligible_members=[v for v in views if v],
        sole_operator=len(members) == 1,
    )


def count_open(db: Session, tenant_id: UUID) -> int:
    set_tenant_scope(db, tenant_id)
    return int(
        db.scalar(
            select(func.count())
            .select_from(DeliveryTask)
            .where(
                DeliveryTask.tenant_id == tenant_id,
                DeliveryTask.status == DeliveryTaskStatus.ASSIGNED.value,
            )
        )
        or 0
    )


def my_work_task(db: Session, tenant_id: UUID, task: DeliveryTask) -> MyWorkTask:
    invoice = db.get(Invoice, task.invoice_id)
    customer = db.get(Customer, task.customer_id)
    return MyWorkTask(
        id=task.id,
        status=task.status,
        official_invoice_number=invoice.official_invoice_number if invoice else None,
        customer_name=customer.name if customer else "?",
        customer_phone=customer.phone if customer else "",
        customer_address=customer.address if customer else None,
        customer_latitude=customer.latitude if customer else None,
        customer_longitude=customer.longitude if customer else None,
        delivery_date=task.delivery_date,
        route_sequence=task.route_sequence,
        currency=task.currency,
        amount_to_collect=(
            amount_to_collect(db, tenant_id, invoice)
            if invoice and task.status == DeliveryTaskStatus.ASSIGNED.value
            else task.amount_to_collect
        ),
        items=task_lines(db, tenant_id, task.invoice_id),
        notes=task.notes,
        version=task.version,
    )


def my_work(db: Session, tenant_id: UUID, membership: TenantMembership) -> MyWorkResponse:
    """Assigned, open tasks of the caller only — the same shape for a driver and for an owner
    acting as operator (PHASE_07.md C/D)."""
    rows = list_tasks(
        db,
        tenant_id,
        status=DeliveryTaskStatus.ASSIGNED.value,
        assigned_membership_id=membership.id,
    )
    return MyWorkResponse(
        tasks=[my_work_task(db, tenant_id, row) for row in rows],
        membership_id=membership.id,
        role=membership.role.value,
    )


def complete_task_row(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    task: DeliveryTask,
    expected_version: int | None,
    note: str | None,
) -> DeliveryTask:
    """Completion without commit (shared by the API and the sync push applier)."""
    if membership.role is not TenantRole.OWNER and task.assigned_membership_id != membership.id:
        raise AppError(
            403, "DELIVERY_TASK_NOT_ASSIGNED", "Only the assigned member can complete it"
        )
    _require_open(task)
    if expected_version is not None:
        _check_version(task, expected_version)
    task.status = DeliveryTaskStatus.COMPLETED.value
    task.completed_at = datetime.now(UTC)
    task.performed_by_membership_id = membership.id
    task.completion_note = note
    task.version += 1
    _audit(
        db,
        tenant_id,
        membership.user_id,
        "delivery_task_completed",
        task.id,
        performed_by_membership_id=membership.id,
    )
    return task
