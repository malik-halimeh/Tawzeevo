"""Scheduled jobs and the in-process scheduler (D-079; PHASE_09.md reliable jobs).

Three jobs run inside the API process for the pilot (a separate worker is a later decision):

- encrypted backups (`run_due_backups`, D-056/D-057) — once per tenant per day;
- storefront view rollup (`rollup_views`, D-051) — raw views older than 90 days folded into
  monthly counts;
- delivery reminders (`run_due_delivery_reminders`, D-049/PHASE_05.md I) — a SCHEDULED reminder
  whose UTC `remind_at` has passed becomes exactly one in-app owner notification.

Every job is idempotent (a second run finds nothing due), tenant-scoped (RLS scope is set per
row), and isolated (one failing tenant is logged and counted, the others still run). Nothing here
touches financial rows.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

from sqlalchemy import select
from sqlalchemy.orm import Session

from tawzeevo_api import metrics
from tawzeevo_api.models import DeliveryReminder, Order, OwnerNotification
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.backup import run_due_backups
from tawzeevo_api.services.storefront_signals import rollup_views

logger = logging.getLogger("tawzeevo.jobs")

DELIVERY_REMINDER_KIND = "DELIVERY_REMINDER"


def run_due_delivery_reminders(db: Session, now: datetime | None = None) -> int:
    """Execute every SCHEDULED reminder whose `remind_at` has passed: one owner notification of
    kind DELIVERY_REMINDER per reminder, then SENT. A reminder whose order is no longer confirmed
    is CANCELLED instead. Each reminder is its own transaction; the row lock (SKIP LOCKED) makes
    concurrent runs and replays safe — a SENT reminder is never sent twice."""
    moment = now or datetime.now(UTC)
    due_ids = list(
        db.scalars(
            select(DeliveryReminder.id)
            .where(DeliveryReminder.status == "SCHEDULED", DeliveryReminder.remind_at <= moment)
            .order_by(DeliveryReminder.remind_at.asc())
        )
    )
    db.rollback()
    sent = 0
    for reminder_id in due_ids:
        try:
            reminder = db.scalar(
                select(DeliveryReminder)
                .where(DeliveryReminder.id == reminder_id, DeliveryReminder.status == "SCHEDULED")
                .with_for_update(skip_locked=True)
            )
            if reminder is None:  # already taken by a concurrent run or rescheduled
                db.rollback()
                continue
            set_tenant_scope(db, reminder.tenant_id)
            order = db.get(Order, reminder.order_id)
            if order is None or order.status != "CONFIRMED":
                reminder.status = "CANCELLED"
                db.commit()
                continue
            db.add(
                OwnerNotification(
                    tenant_id=reminder.tenant_id,
                    kind=DELIVERY_REMINDER_KIND,
                    order_id=reminder.order_id,
                )
            )
            reminder.status = "SENT"
            reminder.sent_at = moment
            db.commit()
            sent += 1
            metrics.increment("reminders_sent")
        except Exception:  # noqa: BLE001 - one reminder must not block the rest
            db.rollback()
            metrics.increment("reminder_failures")
            logger.exception("delivery reminder %s failed", reminder_id)
    return sent


@dataclass
class ScheduledJob:
    name: str
    interval_seconds: int
    run: Callable[[Session], object]
    last_run: float | None = None

    def due(self, now: float) -> bool:
        return self.last_run is None or now - self.last_run >= self.interval_seconds


def default_jobs() -> list[ScheduledJob]:
    return [
        ScheduledJob("delivery_reminders", 300, run_due_delivery_reminders),
        ScheduledJob("backups", 3600, run_due_backups),
        ScheduledJob("view_rollup", 3600, rollup_views),
    ]


def run_due_jobs(
    jobs: list[ScheduledJob], session_factory: Callable[[], Session], now: float | None = None
) -> list[str]:
    """One scheduler tick: run every job whose interval has elapsed, each in its own session so a
    failing job cannot poison another; returns the names that ran."""
    moment = monotonic() if now is None else now
    ran: list[str] = []
    for job in jobs:
        if not job.due(moment):
            continue
        job.last_run = moment
        try:
            with session_factory() as db:
                job.run(db)
            ran.append(job.name)
        except Exception:  # noqa: BLE001 - the scheduler must survive one bad job
            metrics.increment("job_failures")
            logger.exception("scheduled job %s failed", job.name)
    return ran


TICK_SECONDS = 60


def scheduler_loop(
    stop: threading.Event,
    session_factory: Callable[[], Session],
    jobs: list[ScheduledJob] | None = None,
    tick_seconds: int = TICK_SECONDS,
) -> None:
    """In-process scheduler thread body (D-079): wakes every tick and runs the due jobs."""
    table = jobs if jobs is not None else default_jobs()
    while not stop.wait(tick_seconds):
        run_due_jobs(table, session_factory)
