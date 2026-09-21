"""Scheduled jobs under a database role that is subject to row-level security.

The suite's own connection is a superuser, for which `FORCE ROW LEVEL SECURITY` is inert, so it
cannot observe whether a job binds a tenant scope before it reads a tenant-owned table. These
regressions open a second connection as a real `NOSUPERUSER NOBYPASSRLS` login role — the role
`docs/runbooks/database-role.md` tells the owner to provision — and prove that the three
scheduled jobs (delivery reminders D-049, view rollup D-051, encrypted backups D-056/D-057) find
and process exactly the same work under it, tenant by tenant and without cross-tenant mixing.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from test_invoice_editor import _catalog, _owner_context
from test_jobs import _confirmed_order_with_delivery_date
from test_storefront import _publish

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.models import (
    DeliveryReminder,
    OwnerNotification,
    ProductInteraction,
    ProductInteractionRollup,
    TenantBackup,
    TenantBackupConnection,
)
from tawzeevo_api.services import backup as backup_service
from tawzeevo_api.services import storefront_signals
from tawzeevo_api.services.backup import run_due_backups
from tawzeevo_api.services.backup_drive import MEMORY_DRIVE
from tawzeevo_api.services.jobs import DELIVERY_REMINDER_KIND, run_due_delivery_reminders
from tawzeevo_api.services.storefront_signals import rollup_views

MASTER_KEY = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def rls_session_factory(test_engine: Engine) -> Generator[sessionmaker[Session]]:
    """A session factory bound to a throw-away `NOSUPERUSER NOBYPASSRLS` login role.

    The role is created on the disposable test database only, with the grants the runbook
    prescribes, and is dropped again when the test ends.
    """
    role = f"rls_jobs_{uuid4().hex[:12]}"
    secret = uuid4().hex  # disposable, local, test-only
    with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.exec_driver_sql(
            f"CREATE ROLE \"{role}\" LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{secret}'"
        )
        admin.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        admin.exec_driver_sql(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'
        )
        admin.exec_driver_sql(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO "{role}"')
    engine = create_engine(test_engine.url.set(username=role, password=secret), pool_pre_ping=True)
    try:
        with engine.connect() as probe:
            bypasses = probe.execute(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).scalar_one()
            assert bypasses is False, "the regression is meaningless unless RLS really applies"
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f'DROP OWNED BY "{role}"')
            admin.exec_driver_sql(f'DROP ROLE "{role}"')


def _notifications_of(db: Session, tenant_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(OwnerNotification)
            .where(
                OwnerNotification.tenant_id == tenant_id,
                OwnerNotification.kind == DELIVERY_REMINDER_KIND,
            )
        )
        or 0
    )


def test_delivery_reminders_run_under_an_rls_subject_role(
    client, session_factory, rls_session_factory
):
    """Two tenants, one due reminder each: the restricted role sends both, one owner
    notification per tenant, and a replay sends nothing a second time."""
    tenant_a, _token_a, order_a, remind_a = _confirmed_order_with_delivery_date(
        client, session_factory, "rls-jobs-a"
    )
    tenant_b, _token_b, order_b, remind_b = _confirmed_order_with_delivery_date(
        client, session_factory, "rls-jobs-b"
    )
    later = max(remind_a, remind_b) + timedelta(minutes=1)

    with rls_session_factory() as db:
        # Without a bound scope the restricted role sees nothing at all: RLS is really on.
        assert db.scalar(select(func.count()).select_from(DeliveryReminder)) == 0
        sent = run_due_delivery_reminders(db, now=later)
    assert sent == 2

    with session_factory() as db:
        statuses = sorted(db.scalars(select(DeliveryReminder.status)))
        assert statuses == ["SENT", "SENT"]
        assert _notifications_of(db, UUID(tenant_a)) == 1
        assert _notifications_of(db, UUID(tenant_b)) == 1
        orders = sorted(
            str(row)
            for row in db.scalars(
                select(OwnerNotification.order_id).where(
                    OwnerNotification.kind == DELIVERY_REMINDER_KIND
                )
            )
        )
        assert orders == sorted([order_a, order_b])

    # Replay under the same restricted role: nothing is due any more, nothing is duplicated.
    with rls_session_factory() as db:
        assert run_due_delivery_reminders(db, now=later + timedelta(hours=1)) == 0
    with session_factory() as db:
        assert _notifications_of(db, UUID(tenant_a)) == 1
        assert _notifications_of(db, UUID(tenant_b)) == 1


def test_view_rollup_runs_under_an_rls_subject_role_without_mixing_tenants(
    client, session_factory, rls_session_factory
):
    """Raw views of two tenants older than the retention window are folded once, into each
    tenant's own monthly row, and the raw rows are dropped."""
    _owner_a, tenant_a, token_a = _owner_context(client, session_factory, "rls-rollup-a")
    _category_a, product_a, _customer_a = _catalog(client, tenant_a, token_a, name="Cedar Water")
    _publish(client, tenant_a, token_a, product_a["id"])
    _owner_b, tenant_b, token_b = _owner_context(client, session_factory, "rls-rollup-b")
    _category_b, product_b, _customer_b = _catalog(client, tenant_b, token_b, name="Labneh")
    _publish(client, tenant_b, token_b, product_b["id"])

    long_ago = datetime(2026, 5, 3, 10, 0, tzinfo=UTC)
    with session_factory() as db:
        for index in range(3):
            storefront_signals.record_view(
                db, UUID(tenant_a), UUID(product_a["id"]), f"a-{index}", long_ago
            )
        storefront_signals.record_view(
            db, UUID(tenant_b), UUID(product_b["id"]), "b-0", long_ago + timedelta(hours=1)
        )
        assert db.scalar(select(func.count()).select_from(ProductInteraction)) == 4

    moment = datetime(2026, 9, 18, tzinfo=UTC)
    with rls_session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductInteraction)) == 0
        assert rollup_views(db, now=moment) == 4
        # A second run under the same role finds nothing: the job stays idempotent.
        assert rollup_views(db, now=moment) == 0

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductInteraction)) == 0
        rows = {row.tenant_id: row for row in db.scalars(select(ProductInteractionRollup)).all()}
        assert set(rows) == {UUID(tenant_a), UUID(tenant_b)}
        assert rows[UUID(tenant_a)].views == 3
        assert rows[UUID(tenant_a)].tenant_product_id == UUID(product_a["id"])
        assert rows[UUID(tenant_b)].views == 1
        assert rows[UUID(tenant_b)].tenant_product_id == UUID(product_b["id"])
        assert rows[UUID(tenant_a)].month.isoformat() == "2026-05-01"


def test_backup_discovery_runs_under_an_rls_subject_role(
    client, session_factory, rls_session_factory, monkeypatch: pytest.MonkeyPatch
):
    """The connected tenant's backup connection is discovered and backed up under the restricted
    role; a second, unconnected tenant is untouched and never visible without a bound scope."""
    settings: Settings = get_settings().model_copy(
        update={
            "backup_drive_provider": "memory",
            "backup_master_key": MASTER_KEY,
            "backup_kek_id": "kek-test-1",
        }
    )
    monkeypatch.setattr(backup_service, "get_settings", lambda: settings)
    MEMORY_DRIVE.reset()

    from test_backup import _connect  # local import: the module monkeypatches on import time

    _owner_a, tenant_a, token_a = _owner_context(client, session_factory, "rls-backup-a")
    _category, product, _customer = _catalog(client, tenant_a, token_a, name="Cedar Water")
    _publish(client, tenant_a, token_a, product["id"])
    _connect(client, tenant_a, token_a)
    _owner_b, tenant_b, _token_b = _owner_context(client, session_factory, "rls-backup-b")

    moment = datetime(2026, 9, 18, 2, 0, tzinfo=UTC)
    with rls_session_factory() as db:
        # Unscoped, the restricted role sees no connection at all - the job must scope itself.
        assert db.scalar(select(func.count()).select_from(TenantBackupConnection)) == 0
        done = run_due_backups(db, moment, settings)
        assert done == [UUID(tenant_a)]
        # Within one bound scope only that tenant's rows are readable.
        db.rollback()
        db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": tenant_a},
        )
        visible = list(db.scalars(select(TenantBackupConnection.tenant_id)))
        assert visible == [UUID(tenant_a)]
        # A second run inside the 24 h interval is not due again.
        assert run_due_backups(db, moment + timedelta(hours=1), settings) == []

    with session_factory() as db:
        backups = list(db.scalars(select(TenantBackup)))
        assert [row.tenant_id for row in backups] == [UUID(tenant_a)]
        assert backups[0].status == "UPLOADED" and backups[0].kind == "MONTHLY"
        assert (
            db.scalar(
                select(func.count())
                .select_from(TenantBackup)
                .where(TenantBackup.tenant_id == UUID(tenant_b))
            )
            == 0
        )
