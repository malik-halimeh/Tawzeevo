"""Scheduled jobs (audit finding TWZ-F-012; D-049, D-051, D-079): delivery reminders execute as
exactly one owner notification each, the scheduler tick runs backups, the view rollup and the
reminders on their intervals, and one failing job or reminder never blocks the others."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from test_invoice_editor import _auth, _catalog, _owner_context
from test_order_review import _order, _place
from test_storefront import _publish

from tawzeevo_api import metrics
from tawzeevo_api.models import DeliveryReminder, OwnerNotification
from tawzeevo_api.services import jobs
from tawzeevo_api.services.jobs import (
    DELIVERY_REMINDER_KIND,
    ScheduledJob,
    default_jobs,
    run_due_delivery_reminders,
    run_due_jobs,
)


def _confirmed_order_with_delivery_date(client, session_factory, suffix: str):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    placed, _reference = _place(
        client, session_factory, owner, tenant, token, product, phone=customer["phone"]
    )
    order_id = placed["order_id"]
    linked = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/link-customer",
        headers=_auth(token),
        json={"customer_id": customer["id"]},
    )
    assert linked.status_code == 200, linked.text
    detail = _order(client, tenant, token, order_id)
    confirmed = client.post(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/confirm",
        headers=_auth(token),
        json={"expected_revision_id": detail["invoice"]["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    delivery = (datetime.now(UTC) + timedelta(days=2)).date()
    dated = client.put(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": delivery.isoformat()},
    )
    assert dated.status_code == 200, dated.text
    with session_factory() as db:
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.tenant_id == UUID(tenant))
        )
        assert reminder is not None and reminder.status == "SCHEDULED"
        remind_at = reminder.remind_at
    return tenant, token, order_id, remind_at


def _notifications(client, tenant, token):
    response = client.get(f"/api/v1/tenants/{tenant}/notifications", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_due_reminder_becomes_exactly_one_owner_notification_and_replays_are_safe(
    client, session_factory
):
    tenant, token, order_id, remind_at = _confirmed_order_with_delivery_date(
        client, session_factory, "jobs-a"
    )
    tenant_b, token_b, _order_b, remind_at_b = _confirmed_order_with_delivery_date(
        client, session_factory, "jobs-b"
    )
    before = _notifications(client, tenant, token)["unread"]
    metrics.reset_for_tests()

    # Not due yet: nothing happens.
    with session_factory() as db:
        assert run_due_delivery_reminders(db, now=remind_at - timedelta(minutes=1)) == 0
    assert _notifications(client, tenant, token)["unread"] == before

    # Due: one DELIVERY_REMINDER notification per tenant, reminders SENT with a timestamp.
    later = max(remind_at, remind_at_b) + timedelta(minutes=1)
    with session_factory() as db:
        assert run_due_delivery_reminders(db, now=later) == 2
    notes = _notifications(client, tenant, token)
    reminders = [n for n in notes["notifications"] if n["kind"] == DELIVERY_REMINDER_KIND]
    assert len(reminders) == 1 and reminders[0]["order_id"] == order_id
    assert notes["unread"] == before + 1
    other = _notifications(client, tenant_b, token_b)
    assert len([n for n in other["notifications"] if n["kind"] == DELIVERY_REMINDER_KIND]) == 1
    with session_factory() as db:
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.tenant_id == UUID(tenant))
        )
        assert reminder is not None and reminder.status == "SENT" and reminder.sent_at == later
    assert metrics.snapshot()["reminders_sent"] == 2

    # Replay: nothing is due any more, no second notification (idempotent execution).
    with session_factory() as db:
        assert run_due_delivery_reminders(db, now=later + timedelta(hours=1)) == 0
    with session_factory() as db:
        count = db.scalar(
            select(func.count())
            .select_from(OwnerNotification)
            .where(OwnerNotification.kind == DELIVERY_REMINDER_KIND)
        )
        assert count == 2


def test_reminder_of_a_cancelled_order_is_cancelled_and_reschedule_sends_again(
    client, session_factory
):
    tenant, token, order_id, remind_at = _confirmed_order_with_delivery_date(
        client, session_factory, "jobs-c"
    )
    # Re-dating after the reminder was sent schedules a fresh reminder for the new date.
    with session_factory() as db:
        assert run_due_delivery_reminders(db, now=remind_at + timedelta(minutes=1)) == 1
    later_date = (datetime.now(UTC) + timedelta(days=4)).date()
    redated = client.put(
        f"/api/v1/tenants/{tenant}/orders/{order_id}/delivery-date",
        headers=_auth(token),
        json={"delivery_date": later_date.isoformat()},
    )
    assert redated.status_code == 200, redated.text
    with session_factory() as db:
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.order_id == UUID(order_id))
        )
        assert reminder is not None and reminder.status == "SCHEDULED"
        new_remind_at = reminder.remind_at
    # The order is cancelled through the store before the new reminder is due: the reminder is
    # closed instead of notifying about a delivery that will not happen.
    with session_factory() as db:
        from tawzeevo_api.models import Order

        order = db.get(Order, UUID(order_id))
        assert order is not None
        order.status = "CANCELLED"
        db.commit()
    with session_factory() as db:
        assert run_due_delivery_reminders(db, now=new_remind_at + timedelta(minutes=1)) == 0
        reminder = db.scalar(
            select(DeliveryReminder).where(DeliveryReminder.order_id == UUID(order_id))
        )
        assert reminder is not None and reminder.status == "CANCELLED"
    notes = _notifications(client, tenant, token)
    assert len([n for n in notes["notifications"] if n["kind"] == DELIVERY_REMINDER_KIND]) == 1


def test_scheduler_tick_runs_jobs_on_their_intervals_and_isolates_failures(session_factory):
    table = default_jobs()
    assert [(job.name, job.interval_seconds) for job in table] == [
        ("delivery_reminders", 300),
        ("backups", 3600),
        ("view_rollup", 3600),
    ]
    runs: list[str] = []

    def record(name: str):
        def run(db):
            runs.append(name)
            return 0

        return run

    def broken(db):
        raise RuntimeError("boom")

    metrics.reset_for_tests()
    fake = [
        ScheduledJob("fast", 300, record("fast")),
        ScheduledJob("broken", 300, broken),
        ScheduledJob("slow", 3600, record("slow")),
    ]
    assert run_due_jobs(fake, session_factory, now=0.0) == ["fast", "slow"]  # first tick: all due
    assert run_due_jobs(fake, session_factory, now=60.0) == []
    assert run_due_jobs(fake, session_factory, now=300.0) == ["fast"]  # broken failed, fast ran
    assert run_due_jobs(fake, session_factory, now=3600.0) == ["fast", "slow"]
    assert runs == ["fast", "slow", "fast", "fast", "slow"]
    assert metrics.snapshot()["job_failures"] == 3

    # The real job table runs against the database without error on an empty tenant set.
    assert run_due_jobs(default_jobs(), session_factory, now=0.0) == [
        "delivery_reminders",
        "backups",
        "view_rollup",
    ]
    assert jobs.TICK_SECONDS == 60
