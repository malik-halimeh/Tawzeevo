"""Owner order review, confirmation, delivery date and cancellation decisions.

PHASE_05.md G/H/I/J (D-046, D-049, D-063 boundary, D-072). The owner resolves the customer
explicitly (the storefront hint is only a suggestion), edits the draft through the Phase 3 editor,
confirms through the Phase 3 confirmation, sets a tenant-local delivery date only after
confirmation (a reminder job record, never a financial revision), and decides customer
cancellation requests; approval delegates to Phase 3 cancellation accounting. A sole owner with
zero drivers needs nothing else.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    Customer,
    DeliveryReminder,
    Invoice,
    InvoiceRevisionItem,
    InvoiceStatus,
    Order,
    OrderAccessReference,
    OrderCancellationRequest,
    OwnerNotification,
)
from tawzeevo_api.repositories.tenancy import commit_and_restore_tenant_scope, set_tenant_scope
from tawzeevo_api.schemas.cash_van import CustomerCreateRequest
from tawzeevo_api.schemas.invoice_editor import (
    InvoiceCancelRequest,
    InvoiceEditorDraftRequest,
    InvoiceEditorItemRequest,
)
from tawzeevo_api.services.cash_van import create_customer, get_customer
from tawzeevo_api.services.invoice_editor import update_editor_draft
from tawzeevo_api.services.invoice_finance import cancel_invoice, confirm_invoice

TENANT_TZ = ZoneInfo("Asia/Beirut")
REMINDER_LOCAL_TIME = time(hour=9, minute=0)  # the morning before the delivery date, tenant-local
ACTIVE_ORDER_STATES = ("RECEIVED", "CONFIRMED")


def _now() -> datetime:
    return datetime.now(UTC)


def get_order(db: Session, tenant_id: UUID, order_id: UUID) -> Order:
    set_tenant_scope(db, tenant_id)
    order = db.get(Order, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise AppError(404, "ORDER_NOT_FOUND", "Order was not found")
    return order


def list_orders(db: Session, tenant_id: UUID, status: str | None, limit: int = 100) -> list[Order]:
    set_tenant_scope(db, tenant_id)
    query = select(Order).where(Order.tenant_id == tenant_id)
    if status:
        query = query.where(Order.status == status)
    return list(db.scalars(query.order_by(Order.created_at.desc()).limit(limit)))


def candidate_customers(db: Session, tenant_id: UUID, order: Order) -> list[Customer]:
    """Explicit disambiguation list: same normalized phone, never auto-linked."""
    return list(
        db.scalars(
            select(Customer)
            .where(Customer.tenant_id == tenant_id, Customer.phone == order.contact_phone)
            .order_by(Customer.created_at)
        )
    )


def _items_from_revision(
    db: Session, tenant_id: UUID, revision_id: UUID
) -> list[InvoiceEditorItemRequest]:
    rows = db.scalars(
        select(InvoiceRevisionItem)
        .where(
            InvoiceRevisionItem.tenant_id == tenant_id,
            InvoiceRevisionItem.invoice_revision_id == revision_id,
        )
        .order_by(InvoiceRevisionItem.line_number)
    )
    items: list[InvoiceEditorItemRequest] = []
    for row in rows:
        if row.tenant_product_id is not None:
            items.append(
                InvoiceEditorItemRequest(
                    product_id=row.tenant_product_id,
                    barcode=row.barcode,
                    quantity_expression=f"{row.quantity:f}",
                    price_basis=row.price_basis,
                    line_discount_expression=f"{row.line_discount:f}",
                    line_markup_expression=f"{row.line_markup:f}",
                )
            )
        else:
            items.append(
                InvoiceEditorItemRequest(
                    manual_name=row.product_name,
                    manual_unit_price=row.effective_unit_price,
                    quantity_expression=f"{row.quantity:f}",
                    price_basis=row.price_basis,
                    pieces_per_box=row.pieces_per_box,
                    line_discount_expression=f"{row.line_discount:f}",
                    line_markup_expression=f"{row.line_markup:f}",
                )
            )
    return items


def _invoice(db: Session, tenant_id: UUID, order: Order) -> Invoice:
    invoice = db.get(Invoice, order.invoice_id) if order.invoice_id else None
    if invoice is None or invoice.tenant_id != tenant_id:
        raise AppError(409, "ORDER_WITHOUT_INVOICE", "This order has no draft invoice")
    return invoice


def _notify(db: Session, tenant_id: UUID, order_id: UUID, kind: str) -> None:
    db.add(OwnerNotification(id=uuid4(), tenant_id=tenant_id, kind=kind, order_id=order_id))


def link_customer(
    db: Session,
    tenant_id: UUID,
    actor: UUID,
    order_id: UUID,
    *,
    customer_id: UUID | None,
    create: CustomerCreateRequest | None,
    fuzzy_threshold: Decimal,
) -> Order:
    """Explicit owner act: link an existing customer or create one from the snapshot. The draft
    is re-priced through the Phase 3 editor with that customer (grade applies only now)."""
    order = get_order(db, tenant_id, order_id)
    if order.status != "RECEIVED":
        raise AppError(409, "ORDER_NOT_REVIEWABLE", "Only a received order can be linked")
    if (customer_id is None) == (create is None):
        raise AppError(422, "LINK_CHOICE_REQUIRED", "Choose an existing customer or create one")
    if create is not None:
        customer = create_customer(db, tenant_id, create)
    else:
        assert customer_id is not None
        customer = get_customer(db, tenant_id, customer_id)
    invoice = _invoice(db, tenant_id, order)
    request = InvoiceEditorDraftRequest(
        client_command_id=uuid4(),
        expected_predecessor_revision_id=invoice.current_revision_id,
        customer_id=customer.id,
        currency=order.currency,
        reason="owner linked the customer to a storefront order",
        items=_items_from_revision(db, tenant_id, invoice.current_revision_id),
    )
    update_editor_draft(db, tenant_id, actor, invoice.id, request, fuzzy_threshold=fuzzy_threshold)
    order = get_order(db, tenant_id, order_id)
    order.linked_customer_id = customer.id
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="ORDER_CUSTOMER_LINKED",
            entity_type="order",
            entity_id=order.id,
            details={
                "customer_id": str(customer.id),
                "created": create is not None,
                "hint_matched": order.intended_customer_id == customer.id,
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return order


def confirm_order(
    db: Session, tenant_id: UUID, actor: UUID, order_id: UUID, expected_revision_id: UUID
) -> Order:
    order = get_order(db, tenant_id, order_id)
    if order.status != "RECEIVED":
        raise AppError(409, "ORDER_NOT_REVIEWABLE", "Only a received order can be confirmed")
    if order.linked_customer_id is None:
        raise AppError(409, "ORDER_CUSTOMER_REQUIRED", "Link a customer before confirming")
    invoice = _invoice(db, tenant_id, order)
    confirm_invoice(db, tenant_id, actor, invoice.id, expected_revision_id)  # Phase 3 truth
    order = get_order(db, tenant_id, order_id)
    order.status = "CONFIRMED"
    order.decided_at = _now()
    order.decided_by_user_id = actor
    commit_and_restore_tenant_scope(db, tenant_id)
    return order


def decline_order(
    db: Session, tenant_id: UUID, actor: UUID, order_id: UUID, note: str | None
) -> Order:
    order = get_order(db, tenant_id, order_id)
    if order.status != "RECEIVED":
        raise AppError(409, "ORDER_NOT_REVIEWABLE", "Only a received order can be declined")
    invoice = _invoice(db, tenant_id, order)
    cancel_invoice(
        db, tenant_id, actor, invoice.id, InvoiceCancelRequest(idempotency_key=uuid4(), reason=note)
    )
    order = get_order(db, tenant_id, order_id)
    order.status = "DECLINED"
    order.decided_at = _now()
    order.decided_by_user_id = actor
    order.decision_note = note
    commit_and_restore_tenant_scope(db, tenant_id)
    return order


def set_delivery_date(
    db: Session, tenant_id: UUID, actor: UUID, order_id: UUID, delivery_date: date
) -> Order:
    """Only after confirmation; tenant-local date, UTC reminder; no financial revision."""
    order = get_order(db, tenant_id, order_id)
    if order.status != "CONFIRMED":
        raise AppError(409, "ORDER_NOT_CONFIRMED", "Set the delivery date after confirmation")
    if delivery_date < datetime.now(TENANT_TZ).date():
        raise AppError(422, "DELIVERY_DATE_PAST", "Delivery date cannot be in the past")
    order.delivery_date = delivery_date
    remind_local = datetime.combine(delivery_date, REMINDER_LOCAL_TIME, tzinfo=TENANT_TZ)
    remind_at = remind_local.astimezone(UTC)
    reminder = db.scalar(select(DeliveryReminder).where(DeliveryReminder.order_id == order.id))
    if reminder is None:
        db.add(
            DeliveryReminder(
                id=uuid4(),
                tenant_id=tenant_id,
                order_id=order.id,
                delivery_date=delivery_date,
                remind_at=remind_at,
                status="SCHEDULED",
            )
        )
    else:
        reminder.delivery_date = delivery_date
        reminder.remind_at = remind_at
        reminder.status = "SCHEDULED"
        reminder.sent_at = None
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="ORDER_DELIVERY_DATE_SET",
            entity_type="order",
            entity_id=order.id,
            details={
                "delivery_date": delivery_date.isoformat(),
                "remind_at": remind_at.isoformat(),
            },
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return order


# ---------------------------------------------------------------------------------------------
# Cancellation requests (J)
# ---------------------------------------------------------------------------------------------


def request_cancellation(
    db: Session, reference: OrderAccessReference, reason: str | None
) -> OrderCancellationRequest:
    """Customer request through the provisional reference; the owner decides."""
    order = db.get(Order, reference.order_id)
    if order is None or order.status not in ACTIVE_ORDER_STATES:
        raise AppError(409, "ORDER_NOT_CANCELLABLE", "This order can no longer be cancelled")
    pending = db.scalar(
        select(OrderCancellationRequest).where(
            OrderCancellationRequest.order_id == order.id,
            OrderCancellationRequest.status == "PENDING",
        )
    )
    if pending is not None:
        return pending
    request = OrderCancellationRequest(
        id=uuid4(), tenant_id=order.tenant_id, order_id=order.id, status="PENDING", reason=reason
    )
    db.add(request)
    _notify(db, order.tenant_id, order.id, "CANCELLATION_REQUESTED")
    commit_and_restore_tenant_scope(db, order.tenant_id)
    return request


def decide_cancellation(
    db: Session, tenant_id: UUID, actor: UUID, request_id: UUID, *, approve: bool, note: str | None
) -> OrderCancellationRequest:
    set_tenant_scope(db, tenant_id)
    request = db.get(OrderCancellationRequest, request_id)
    if request is None or request.tenant_id != tenant_id:
        raise AppError(404, "CANCELLATION_REQUEST_NOT_FOUND", "Request was not found")
    if request.status != "PENDING":
        raise AppError(409, "CANCELLATION_REQUEST_DECIDED", "This request was already decided")
    order = get_order(db, tenant_id, request.order_id)
    if approve:
        invoice = _invoice(db, tenant_id, order)
        if invoice.status is not InvoiceStatus.CANCELLED:
            cancel_invoice(
                db,
                tenant_id,
                actor,
                invoice.id,
                InvoiceCancelRequest(idempotency_key=uuid4(), reason=note or request.reason),
            )  # Phase 3 reversal accounting for confirmed invoices; drafts just close
        order = get_order(db, tenant_id, order_id=request.order_id)
        order.status = "CANCELLED"
        order.decided_at = _now()
        order.decided_by_user_id = actor
        order.decision_note = note
        reminder = db.scalar(select(DeliveryReminder).where(DeliveryReminder.order_id == order.id))
        if reminder is not None and reminder.status == "SCHEDULED":
            reminder.status = "CANCELLED"
    request = db.get(OrderCancellationRequest, request_id)
    assert request is not None
    request.status = "APPROVED" if approve else "REJECTED"
    request.decided_at = _now()
    request.decided_by_user_id = actor
    request.decision_note = note
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="ORDER_CANCELLATION_" + request.status,
            entity_type="order",
            entity_id=request.order_id,
            details={"request_id": str(request.id)},
        )
    )
    commit_and_restore_tenant_scope(db, tenant_id)
    return request


def list_cancellation_requests(
    db: Session, tenant_id: UUID, order_id: UUID
) -> list[OrderCancellationRequest]:
    return list(
        db.scalars(
            select(OrderCancellationRequest)
            .where(
                OrderCancellationRequest.tenant_id == tenant_id,
                OrderCancellationRequest.order_id == order_id,
            )
            .order_by(OrderCancellationRequest.created_at.desc())
        )
    )


def list_notifications(
    db: Session, tenant_id: UUID, unread_only: bool, limit: int = 50
) -> list[OwnerNotification]:
    set_tenant_scope(db, tenant_id)
    query = select(OwnerNotification).where(OwnerNotification.tenant_id == tenant_id)
    if unread_only:
        query = query.where(OwnerNotification.read_at.is_(None))
    return list(db.scalars(query.order_by(OwnerNotification.created_at.desc()).limit(limit)))


def mark_notification_read(
    db: Session, tenant_id: UUID, notification_id: UUID
) -> OwnerNotification:
    set_tenant_scope(db, tenant_id)
    row = db.get(OwnerNotification, notification_id)
    if row is None or row.tenant_id != tenant_id:
        raise AppError(404, "NOTIFICATION_NOT_FOUND", "Notification was not found")
    if row.read_at is None:
        row.read_at = _now()
        commit_and_restore_tenant_scope(db, tenant_id)
    return row
