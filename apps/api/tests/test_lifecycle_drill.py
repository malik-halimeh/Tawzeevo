"""Phase 9 P9-M2 (PHASE_09.md D/E): the controlled lifecycle drill and the migration rehearsal.

Lifecycle: export → suspend (every member, device and private link locked; storefront stops
taking orders) → reactivate → export again byte-for-byte equal → deliberate close (retyped name,
terminal, storefront gone, data retained). Migration: a database built to the Phase 7 head is
upgraded to the current head — the production-like path — without editing applied migrations."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from test_delivery_tasks import _driver, _post
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _login, _owner_context
from test_procurement import _confirm_invoice
from test_storefront import _publish, _slug

from alembic import command
from tawzeevo_api.models import Tenant, TenantStatus
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.backup_export import export_tenant


def _export(session_factory, tenant: str) -> tuple[str, dict[str, int]]:
    with session_factory() as db:
        set_tenant_scope(db, UUID(tenant))
        payload, counts = export_tenant(db, UUID(tenant))
    return json.dumps(payload, sort_keys=True, default=str), counts


def test_lifecycle_drill_suspend_reactivate_preserves_data_and_close_is_terminal(
    client, session_factory
):
    owner, tenant, token = _owner_context(client, session_factory, "drill")
    admin = _auth(_login(client, "admin-drill@example.com"))
    _category, product, customer = _catalog(client, tenant, token, name="Drill Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "2")
    link = _post(client, tenant, token, f"/api/v1/invoices/{confirmed['id']}/capabilities", {})
    secret = link.json()["public_path"].split("#", 1)[1]
    _d, driver_token, _m = _driver(client, session_factory, tenant, "driver-drill@example.com")
    device = {
        "device_installation_id": str(uuid4()),
        "protocol_version": 1,
        "app_schema_version": 1,
    }
    assert _post(client, tenant, token, "/api/v1/sync/bootstrap", device).status_code == 200

    before, counts = _export(session_factory, tenant)
    assert counts["invoices"] == 1 and counts["customers"] == 1

    # Suspension: owner, driver, device and private link are locked; storefront stops orders.
    suspended = client.post(f"/api/v1/platform/tenants/{tenant}/suspend", headers=admin)
    assert suspended.status_code == 200, suspended.text
    for member_token in (token, driver_token):
        denied = client.get(
            f"/api/v1/delivery-tasks/my-work?tenant_id={tenant}", headers=_auth(member_token)
        )
        assert denied.status_code == 403
    assert _post(client, tenant, token, "/api/v1/sync/bootstrap", device).status_code == 403
    assert (
        client.get(
            "/api/v1/public/invoice/data", headers={"X-Invoice-Capability": secret}
        ).status_code
        == 404
    )
    shop = client.get(f"/api/v1/public/{slug}/catalog")
    assert shop.status_code == 200 and shop.json()["accepting_orders"] is False

    # Reactivation restores access and every row is exactly as before (nothing was deleted).
    reactivated = client.post(f"/api/v1/platform/tenants/{tenant}/reactivate", headers=admin)
    assert reactivated.status_code == 200, reactivated.text
    after, counts_after = _export(session_factory, tenant)
    assert counts_after == counts
    # Device registrations were revoked on suspension (PHASE_04.md B) — that is the one expected
    # difference; everything else is identical.
    before_rows = json.loads(before)
    after_rows = json.loads(after)
    changed = {name for name in before_rows if before_rows[name] != after_rows[name]}
    assert changed <= {"sync_devices"}, changed
    assert (
        client.get(
            f"/api/v1/delivery-tasks/my-work?tenant_id={tenant}", headers=_auth(token)
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/public/invoice/data", headers={"X-Invoice-Capability": secret}
        ).status_code
        == 200
    )

    # Deliberate closure: retyped name, admin-only, terminal; data retained, storefront gone.
    wrong = client.post(
        f"/api/v1/platform/tenants/{tenant}/close",
        headers=admin,
        json={"reason": "Owner asked to close", "confirm_business_name": "Not the name"},
    )
    assert (
        wrong.status_code == 400 and wrong.json()["detail"]["code"] == "CLOSE_CONFIRMATION_MISMATCH"
    )
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant}/close",
            headers=_auth(token),
            json={"reason": "x", "confirm_business_name": "Route drill"},
        ).status_code
        == 403
    )
    closed = client.post(
        f"/api/v1/platform/tenants/{tenant}/close",
        headers=admin,
        json={"reason": "Owner asked to close", "confirm_business_name": "route DRILL"},
    )
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED"
    assert (
        client.post(f"/api/v1/platform/tenants/{tenant}/reactivate", headers=admin).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant}/close",
            headers=admin,
            json={"reason": "again", "confirm_business_name": "Route drill"},
        ).status_code
        == 409
    )
    denied = client.get(f"/api/v1/delivery-tasks/my-work?tenant_id={tenant}", headers=_auth(token))
    assert denied.status_code == 403 and denied.json()["detail"]["code"] == "TENANT_CLOSED"
    assert client.get(f"/api/v1/public/{slug}/catalog").status_code == 404
    assert (
        client.get(
            "/api/v1/public/invoice/data", headers={"X-Invoice-Capability": secret}
        ).status_code
        == 404
    )
    final, counts_final = _export(session_factory, tenant)
    assert counts_final == counts  # retention: nothing deleted by closure
    with session_factory() as db:
        row = db.get(Tenant, UUID(tenant))
        assert row is not None and row.status is TenantStatus.CLOSED and row.closed_at is not None


def test_production_like_upgrade_from_the_phase7_head(test_engine) -> None:
    """Build a database to the Phase 7 head, then upgrade to the current head (expand-only)."""
    database_name = f"tawzeevo_upgrade_{uuid4().hex[:12]}"
    admin_engine = create_engine(test_engine.url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    target_url = test_engine.url.set(database=database_name)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url", target_url.render_as_string(hide_password=False).replace("%", "%%")
    )
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        command.upgrade(config, "20260919_0026")
        with target_engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "20260919_0026"
            )
            tables_before = set(inspect(connection).get_table_names())
        command.upgrade(config, "head")
        with target_engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "20260921_0031"
            )
            tables_after = set(inspect(connection).get_table_names())
        # Phase 8/9 only added structures; nothing from Phase 7 was dropped or renamed.
        assert tables_before <= tables_after
        assert {"tenant_branding", "password_reset_tokens", "customer_verified_sessions"} <= (
            tables_after - tables_before
        )
    finally:
        target_engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin_engine.dispose()
