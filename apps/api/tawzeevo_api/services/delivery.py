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
    ProcurementItem,
    ProcurementList,
    TenantMembership,
    TenantRole,
    TenantSupplier,
    User,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.delivery import (
    AssigneeView,
    EligibleInvoice,
    LocationUpdateRequest,
    LocationView,
    MyWorkResponse,
    MyWorkTask,
    NearbyItem,
    NearbyResponse,
    NearbySupplier,
    SuggestedStop,
    SuggestOrderRequest,
    SuggestOrderResponse,
    TaskCreateRequest,
    TaskLine,
    TaskListResponse,
    TaskResponse,
)
from tawzeevo_api.services.invoice_editor import money
from tawzeevo_api.services.procurement import _line_is_settled
from tawzeevo_api.services.routing import Stop, haversine_m, suggest_order

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


def get_task(
    db: Session, tenant_id: UUID, task_id: UUID, *, for_update: bool = False
) -> DeliveryTask:
    """`for_update` locks the row for a state transition so two concurrent transitions with the
    same expected version serialize: the second one sees the bumped version and gets 409."""
    set_tenant_scope(db, tenant_id)
    row = db.get(DeliveryTask, task_id, with_for_update=for_update or None)
    if row is None or row.tenant_id != tenant_id:
        raise AppError(404, "DELIVERY_TASK_NOT_FOUND", "Delivery task was not found")
    if for_update:
        db.refresh(row)  # the locked row's current version, not a stale identity-map copy
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
    task = get_task(db, tenant_id, task_id, for_update=True)
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
    task = get_task(db, tenant_id, task_id, for_update=True)
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
    task = get_task(db, tenant_id, task_id, for_update=True)
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
    task = get_task(db, tenant_id, task_id, for_update=True)
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


# ---------------------------------------------------------------------------------------------
# Locations (PHASE_07.md E; D-061), stop order (F/G; D-060), nearby suppliers (H)
# ---------------------------------------------------------------------------------------------

GPS_GOOD_ACCURACY_M = Decimal("50")
_SOURCE_RANK = {"gps": 3, "geocoded": 2, "manual": 1}


def _reading_rank(source: str | None, accuracy: Decimal | None) -> int:
    """Among unconfirmed readings (D-061): GPS better than 50 m beats geocoded beats manual;
    a loose GPS reading ranks below geocoded."""
    if source == "gps":
        return 3 if accuracy is not None and accuracy < GPS_GOOD_ACCURACY_M else 1
    return _SOURCE_RANK.get(source or "", 0)


def location_view(customer: Customer) -> LocationView:
    return LocationView(
        latitude=customer.latitude,
        longitude=customer.longitude,
        source=customer.location_source,
        captured_at=customer.location_captured_at,
        accuracy_meters=customer.location_accuracy_meters,
        confirmed_at=customer.location_confirmed_at,
    )


def _authorized_task(
    db: Session, tenant_id: UUID, membership: TenantMembership, task_id: UUID
) -> DeliveryTask:
    task = get_task(db, tenant_id, task_id)
    if membership.role is not TenantRole.OWNER and task.assigned_membership_id != membership.id:
        raise AppError(403, "DELIVERY_TASK_NOT_ASSIGNED", "Only the assigned member may do this")
    return task


def update_task_location(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    task_id: UUID,
    request: LocationUpdateRequest,
) -> tuple[bool, str, Customer]:
    """Owner or the assigned member records a reading for the task's customer. A confirmed
    location is only replaced by another confirmed reading; among unconfirmed readings a worse
    one never replaces a better one silently. Only the current best is stored, no history."""
    task = _authorized_task(db, tenant_id, membership, task_id)
    _require_open(task)
    customer = db.get(Customer, task.customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        raise AppError(404, "CUSTOMER_NOT_FOUND", "Customer was not found")
    now = datetime.now(UTC)
    if customer.location_confirmed_at is not None and not request.confirm:
        return False, "CONFIRMED_LOCATION_KEPT", customer
    if (
        customer.latitude is not None
        and customer.location_confirmed_at is None
        and not request.confirm
        and _reading_rank(request.source, request.accuracy_meters)
        < _reading_rank(customer.location_source, customer.location_accuracy_meters)
    ):
        return False, "BETTER_READING_KEPT", customer
    customer.latitude = request.latitude
    customer.longitude = request.longitude
    customer.location_source = request.source
    customer.location_captured_at = now
    customer.location_accuracy_meters = request.accuracy_meters
    if request.confirm:
        customer.location_confirmed_at = now
        customer.location_confirmed_by_membership_id = membership.id
    else:
        customer.location_confirmed_at = None
        customer.location_confirmed_by_membership_id = None
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=membership.user_id,
            action="customer_location_updated",
            entity_type="customer",
            entity_id=customer.id,
            details={
                "task_id": str(task.id),
                "source": request.source,
                "accuracy_meters": str(request.accuracy_meters or ""),
                "confirmed": str(request.confirm),
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    db.refresh(customer)
    return True, "CONFIRMED" if request.confirm else "APPLIED", customer


def _member_tasks(
    db: Session, tenant_id: UUID, membership: TenantMembership, task_ids: list[UUID]
) -> list[DeliveryTask]:
    tasks = [get_task(db, tenant_id, task_id) for task_id in task_ids]
    for task in tasks:
        if membership.role is not TenantRole.OWNER and task.assigned_membership_id != membership.id:
            raise AppError(403, "DELIVERY_TASK_NOT_ASSIGNED", "Only your own stops can be ordered")
    return tasks


def suggest_stop_order(
    db: Session, tenant_id: UUID, membership: TenantMembership, request: SuggestOrderRequest
) -> SuggestOrderResponse:
    tasks = _member_tasks(db, tenant_id, membership, request.task_ids)
    customer_ids = [task.customer_id for task in tasks]
    customers = {
        row.id: row for row in db.scalars(select(Customer).where(Customer.id.in_(customer_ids)))
    }
    located: list[Stop] = []
    unlocated: list[UUID] = []
    for task in tasks:
        customer = customers.get(task.customer_id)
        if (
            customer is not None
            and customer.latitude is not None
            and customer.longitude is not None
        ):
            located.append(Stop(task.id, float(customer.latitude), float(customer.longitude)))
        else:
            unlocated.append(task.id)
    if request.origin is not None:
        origin = (float(request.origin.latitude), float(request.origin.longitude))
    elif located:
        origin = (located[0].latitude, located[0].longitude)
    else:
        origin = (0.0, 0.0)
    ordered, method, note = suggest_order(origin, located, allow_online=request.allow_online)
    by_task = {task.id: task for task in tasks}
    stops: list[SuggestedStop] = []
    for index, stop in enumerate(ordered, start=1):
        customer = customers.get(by_task[stop.id].customer_id)
        stops.append(
            SuggestedStop(
                task_id=stop.id,
                sequence=index,
                customer_name=customer.name if customer else "?",
                latitude=customer.latitude if customer else None,
                longitude=customer.longitude if customer else None,
                has_location=True,
            )
        )
    for offset, task_id in enumerate(unlocated, start=len(stops) + 1):
        customer = customers.get(by_task[task_id].customer_id)
        stops.append(
            SuggestedStop(
                task_id=task_id,
                sequence=offset,
                customer_name=customer.name if customer else "?",
                latitude=None,
                longitude=None,
                has_location=False,
            )
        )
    return SuggestOrderResponse(method=method, note=note, stops=stops, unlocated_task_ids=unlocated)


def save_stop_order(
    db: Session, tenant_id: UUID, membership: TenantMembership, task_ids: list[UUID]
) -> list[DeliveryTask]:
    """Manual reorder or an accepted suggestion: sequence 1..n on the given open tasks."""
    tasks = _member_tasks(db, tenant_id, membership, task_ids)
    for sequence, task in enumerate(tasks, start=1):
        if task.status != DeliveryTaskStatus.ASSIGNED.value:
            raise AppError(409, "DELIVERY_TASK_CLOSED", "Only open deliveries can be ordered")
        if task.route_sequence != sequence:
            task.route_sequence = sequence
            task.version += 1
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=membership.user_id,
            action="delivery_route_ordered",
            entity_type="delivery_task",
            entity_id=tasks[0].id,
            details={"count": str(len(tasks))},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return [get_task(db, tenant_id, task.id) for task in tasks]


def nearby_suppliers(
    db: Session,
    tenant_id: UUID,
    membership: TenantMembership,
    latitude: float,
    longitude: float,
    radius_m: int,
) -> NearbyResponse:
    """Suppliers with a saved location within the radius that have an open pickup need
    (PHASE_07.md H). Owners see every open list; a driver only the lists assigned to them.
    Never a price here: the owner opens the supplier desk for that."""
    set_tenant_scope(db, tenant_id)
    query = select(ProcurementList).where(
        ProcurementList.tenant_id == tenant_id,
        ProcurementList.status.in_(["OPEN", "PARTIALLY_PURCHASED"]),
    )
    if membership.role is not TenantRole.OWNER:
        query = query.where(ProcurementList.assignee_membership_id == membership.id)
    lists = list(db.scalars(query))
    needs: dict[UUID, list[NearbyItem]] = {}
    for procurement_list in lists:
        for item in db.scalars(
            select(ProcurementItem).where(
                ProcurementItem.tenant_id == tenant_id,
                ProcurementItem.list_id == procurement_list.id,
            )
        ):
            if item.supplier_id is None or _line_is_settled(item):
                continue
            needs.setdefault(item.supplier_id, []).append(
                NearbyItem(
                    product_name=item.product_name,
                    remaining_quantity=item.remaining_quantity,
                    price_basis=item.price_basis,
                    pieces_per_box=item.pieces_per_box,
                    list_title=procurement_list.title,
                )
            )
    suppliers: list[NearbySupplier] = []
    if needs:
        for supplier in db.scalars(
            select(TenantSupplier).where(
                TenantSupplier.tenant_id == tenant_id, TenantSupplier.id.in_(list(needs))
            )
        ):
            if supplier.latitude is None or supplier.longitude is None:
                continue
            distance = haversine_m(
                latitude, longitude, float(supplier.latitude), float(supplier.longitude)
            )
            if distance > radius_m:
                continue
            suppliers.append(
                NearbySupplier(
                    supplier_id=supplier.id,
                    supplier_name=supplier.name,
                    contact_phone=supplier.contact_phone,
                    address=supplier.address,
                    latitude=supplier.latitude,
                    longitude=supplier.longitude,
                    distance_meters=int(round(distance)),
                    items=needs[supplier.id],
                )
            )
    suppliers.sort(key=lambda row: (row.distance_meters, row.supplier_name))
    return NearbyResponse(radius_meters=radius_m, suppliers=suppliers)
