"""One delivery date per order (D-104): the order's delivery date and its open delivery's date are
kept equal, in the same transaction, whichever of the two the owner changes. No commit here; the
caller's transaction carries both changes and their audit entries."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tawzeevo_api.models import (
    AuditEvent,
    DeliveryReminder,
    DeliveryTask,
    DeliveryTaskStatus,
    Order,
)

TENANT_TZ = ZoneInfo("Asia/Beirut")
REMINDER_LOCAL_TIME = time(hour=9, minute=0)  # the morning before the delivery date, tenant-local


def schedule_reminder(
    db: Session, tenant_id: UUID, order: Order, delivery_date: date | None
) -> str | None:
    """The order's reminder follows its delivery date; no date cancels it. Returns remind_at."""
    reminder = db.scalar(select(DeliveryReminder).where(DeliveryReminder.order_id == order.id))
    if delivery_date is None:
        if reminder is not None and reminder.status == "SCHEDULED":
            reminder.status = "CANCELLED"
        return None
    remind_at = datetime.combine(delivery_date, REMINDER_LOCAL_TIME, tzinfo=TENANT_TZ).astimezone(
        UTC
    )
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
    return remind_at.isoformat()


def follow_order_date(
    db: Session, tenant_id: UUID, actor: UUID | None, order: Order, delivery_date: date
) -> None:
    """The order's date changed: its open delivery (if any) takes the same date, with a version bump
    and an audit entry naming the order as the source."""
    conditions = [DeliveryTask.order_id == order.id]
    if order.invoice_id is not None:
        conditions.append(DeliveryTask.invoice_id == order.invoice_id)
    tasks = db.scalars(
        select(DeliveryTask)
        .where(
            DeliveryTask.tenant_id == tenant_id,
            DeliveryTask.status == DeliveryTaskStatus.ASSIGNED.value,
            or_(*conditions),
        )
        .with_for_update()
    ).all()
    for task in tasks:
        if task.delivery_date == delivery_date:
            continue
        task.delivery_date = delivery_date
        task.version += 1
        db.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_user_id=actor,
                action="delivery_task_updated",
                entity_type="delivery_task",
                entity_id=task.id,
                details={"delivery_date": delivery_date.isoformat(), "source": f"order:{order.id}"},
            )
        )


def follow_task_date(
    db: Session, tenant_id: UUID, actor: UUID | None, task: DeliveryTask, delivery_date: date | None
) -> None:
    """A delivery's date changed: the order it came from takes the same date (and its reminder
    follows), with an audit entry naming the delivery as the source."""
    order = None
    if task.order_id is not None:
        order = db.get(Order, task.order_id)
    if order is None:
        order = db.scalar(
            select(Order).where(Order.tenant_id == tenant_id, Order.invoice_id == task.invoice_id)
        )
    if order is None or order.tenant_id != tenant_id or order.delivery_date == delivery_date:
        return
    order.delivery_date = delivery_date
    remind_at = schedule_reminder(db, tenant_id, order, delivery_date)
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor,
            action="ORDER_DELIVERY_DATE_SET",
            entity_type="order",
            entity_id=order.id,
            details={
                "delivery_date": delivery_date.isoformat() if delivery_date else "",
                "remind_at": remind_at or "",
                "source": f"delivery_task:{task.id}",
            },
        )
    )
