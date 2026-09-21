"""P4-M5: encrypted Google backup with the in-memory Drive double (D-055, D-056, D-057)."""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _login,
    _owner_context,
    _user,
)

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.models import (
    CustomerLedgerEntry,
    Invoice,
    SystemUserType,
    Tenant,
    TenantBackup,
    TenantBackupConnection,
    TenantBackupRestore,
)
from tawzeevo_api.services import backup as backup_service
from tawzeevo_api.services.backup_drive import MEMORY_DRIVE, SCOPES
from tawzeevo_api.services.backup_export import EXPORTED_MODELS

MASTER_KEY = base64.b64encode(os.urandom(32)).decode()
OTHER_KEY = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture(autouse=True)
def memory_backup_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = get_settings().model_copy(
        update={
            "backup_drive_provider": "memory",
            "backup_master_key": MASTER_KEY,
            "backup_kek_id": "kek-test-1",
        }
    )
    monkeypatch.setattr(backup_service, "get_settings", lambda: settings)
    MEMORY_DRIVE.reset()
    return settings


def _connect(client, tenant, token, email="owner.drive@example.com"):
    authorize = client.post(
        f"/api/v1/tenants/{tenant}/backup/google/authorize", headers=_auth(token)
    )
    assert authorize.status_code == 200, authorize.text
    assert authorize.json()["scope"] == SCOPES
    assert "drive.file" in authorize.json()["authorization_url"]
    state = parse_qs(urlparse(authorize.json()["authorization_url"]).query)["state"][0]
    code = MEMORY_DRIVE.issue_code(email)
    connected = client.post(
        f"/api/v1/tenants/{tenant}/backup/google/connect",
        headers=_auth(token),
        json={"code": code, "state": state},
    )
    assert connected.status_code == 201, connected.text
    return connected.json()


def _business_data(client, session_factory, owner, tenant, token):
    _category, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    draft = client.post(
        f"/api/v1/invoices?tenant_id={tenant}",
        headers=_auth(token),
        json=_confirmable_payload(customer["id"], product["id"]),
    )
    assert draft.status_code == 201, draft.text
    confirmed = client.post(
        f"/api/v1/invoices/{draft.json()['id']}/confirm?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_revision_id": draft.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    receipt = client.post(
        "/api/v1/payments/customer-receipts",
        params={"tenant_id": tenant},
        headers=_auth(token),
        json={
            "idempotency_key": str(uuid4()),
            "customer_id": customer["id"],
            "amount": "10.0000",
            "currency": "USD",
            "method": "CASH",
            "paid_at": datetime.now(UTC).isoformat(),
        },
    )
    assert receipt.status_code == 201, receipt.text
    return customer, confirmed.json()


def _row_counts(session_factory, tenant) -> dict[str, int]:
    with session_factory() as db:
        counts = {}
        for model in EXPORTED_MODELS:
            table = model.__table__
            counts[table.name] = int(
                db.scalar(
                    select(func.count()).select_from(table).where(table.c.tenant_id == UUID(tenant))
                )
            )
        return counts


def test_connect_backup_verify_and_status(client, session_factory, monkeypatch):
    owner, tenant, token = _owner_context(client, session_factory, "backup")
    customer, invoice = _business_data(client, session_factory, owner, tenant, token)
    connection = _connect(client, tenant, token)
    assert connection["folder_name"].startswith("Tawzeevo Backup – Route backup")
    assert connection["account_email"] == "owner.drive@example.com"
    with session_factory() as db:
        stored = db.scalar(select(TenantBackupConnection))
        assert stored is not None
        # The refresh token is never stored in clear.
        refresh_tokens = list(MEMORY_DRIVE.accounts)
        assert refresh_tokens and refresh_tokens[0].encode() not in stored.wrapped_refresh_token

    run = client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token))
    assert run.status_code == 201, run.text
    backup = run.json()
    assert backup["status"] == "UPLOADED" and backup["kind"] == "MANUAL"
    manifest = backup["manifest"]
    assert manifest["encryption"]["algorithm"] == "AES-256-GCM"
    assert manifest["encryption"]["kek_id"] == "kek-test-1"
    assert manifest["migration_version"] == "20260921_0030"
    assert manifest["counts"] == _row_counts(session_factory, tenant)
    assert manifest["counts"]["invoices"] == 1 and manifest["counts"]["payments"] == 1
    # The Drive file holds ciphertext only: no customer name, phone or invoice number in clear.
    (folder, name, blob), *_ = MEMORY_DRIVE.files.values()
    assert name == backup["file_name"] and len(blob) == backup["byte_size"]
    for secret in (customer["name"], customer["phone"], invoice["official_invoice_number"]):
        assert secret.encode() not in blob

    verify = client.post(
        f"/api/v1/tenants/{tenant}/backup/{backup['id']}/verify", headers=_auth(token)
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["mode"] == "VERIFY" and verify.json()["status"] == "VERIFIED"
    assert verify.json()["report"]["consistent"] is True
    assert verify.json()["report"]["rows"] == sum(manifest["counts"].values())
    # A drill changes nothing.
    assert _row_counts(session_factory, tenant) == manifest["counts"]

    status = client.get(f"/api/v1/tenants/{tenant}/backup", headers=_auth(token))
    assert status.status_code == 200
    body = status.json()
    assert body["connection"]["id"] == connection["id"]
    assert body["latest_backup"]["id"] == backup["id"]
    assert body["latest_restore"]["status"] == "VERIFIED"
    assert body["retention"] == {"daily": 30, "monthly": 12}

    # Retention (D-056): only the newest N daily/manual backups survive, files are deleted.
    monkeypatch.setattr(backup_service, "DAILY_RETENTION", 2)
    second = client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token)).json()
    third = client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token)).json()
    history = client.get(f"/api/v1/tenants/{tenant}/backup", headers=_auth(token)).json()
    by_id = {row["id"]: row["status"] for row in history["backups"]}
    assert by_id == {backup["id"]: "DELETED", second["id"]: "UPLOADED", third["id"]: "UPLOADED"}
    assert {name for _f, name, _b in MEMORY_DRIVE.files.values()} == {
        second["file_name"],
        third["file_name"],
    }

    # Another tenant's owner sees nothing of this tenant's backups.
    _other_owner, other_tenant, other_token = _owner_context(client, session_factory, "other")
    foreign = client.post(
        f"/api/v1/tenants/{other_tenant}/backup/{third['id']}/verify", headers=_auth(other_token)
    )
    assert foreign.status_code == 404
    crossed = client.get(f"/api/v1/tenants/{tenant}/backup", headers=_auth(other_token))
    assert crossed.status_code == 403

    # Disconnecting forgets the token; a run is refused until reconnected.
    gone = client.post(f"/api/v1/tenants/{tenant}/backup/google/disconnect", headers=_auth(token))
    assert gone.status_code == 204
    refused = client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token))
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "BACKUP_NOT_CONNECTED"
    _connect(client, tenant, token, email="owner.second@example.com")
    assert (
        client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token)).status_code == 201
    )


def test_tampered_file_and_wrong_master_key_fail_safely(client, session_factory, monkeypatch):
    owner, tenant, token = _owner_context(client, session_factory, "tamper")
    _business_data(client, session_factory, owner, tenant, token)
    _connect(client, tenant, token)
    backup = client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token)).json()
    file_id = backup["manifest"] and next(iter(MEMORY_DRIVE.files))

    MEMORY_DRIVE.tamper(file_id)
    tampered = client.post(
        f"/api/v1/tenants/{tenant}/backup/{backup['id']}/verify", headers=_auth(token)
    )
    assert tampered.status_code == 409, tampered.text
    assert tampered.json()["detail"]["code"] == "BACKUP_INTEGRITY_FAILED"
    MEMORY_DRIVE.tamper(file_id)  # flip back: checksum matches again

    # Same checksum, but a wrong master key cannot unwrap the tenant key.
    wrong = backup_service.get_settings().model_copy(update={"backup_master_key": OTHER_KEY})
    monkeypatch.setattr(backup_service, "get_settings", lambda: wrong)
    wrong_key = client.post(
        f"/api/v1/tenants/{tenant}/backup/{backup['id']}/verify", headers=_auth(token)
    )
    assert wrong_key.status_code == 409
    assert wrong_key.json()["detail"]["code"] == "BACKUP_INTEGRITY_FAILED"
    with session_factory() as db:
        outcomes = list(db.scalars(select(TenantBackupRestore.status)))
        assert outcomes == ["FAILED", "FAILED"]
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1


def test_import_fills_only_an_empty_tenant_and_devices_rebootstrap(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "restore")
    customer, invoice = _business_data(client, session_factory, owner, tenant, token)
    _connect(client, tenant, token)
    backup = client.post(f"/api/v1/tenants/{tenant}/backup/run", headers=_auth(token)).json()
    before = _row_counts(session_factory, tenant)
    admin = _user(session_factory, "restore.admin@example.com", SystemUserType.ADMIN)
    admin_token = _login(client, admin.email)
    path = f"/api/v1/platform/tenants/{tenant}/backups/{backup['id']}/import"

    # Owners cannot import; administrators must confirm the tenant; live data is never overwritten.
    assert (
        client.post(path, headers=_auth(token), json={"confirm_tenant_id": tenant}).status_code
        == 403
    )
    mismatch = client.post(
        path, headers=_auth(admin_token), json={"confirm_tenant_id": str(uuid4())}
    )
    assert mismatch.status_code == 400
    live = client.post(path, headers=_auth(admin_token), json={"confirm_tenant_id": tenant})
    assert live.status_code == 409 and live.json()["detail"]["code"] == "BACKUP_TARGET_NOT_EMPTY"
    assert _row_counts(session_factory, tenant) == before

    # Disaster: the business tables are lost (platform users and memberships remain).
    # Financial rows are immutable (no DELETE), so the loss is simulated the way a real one
    # happens: the tables are gone and re-created empty in the recovery environment.
    with session_factory() as db:
        names = ", ".join(model.__table__.name for model in EXPORTED_MODELS)
        db.execute(text(f"TRUNCATE TABLE {names} CASCADE"))
        db.commit()
    assert sum(_row_counts(session_factory, tenant).values()) == 0
    missing = client.get(
        f"/api/v1/invoices/{invoice['id']}?tenant_id={tenant}", headers=_auth(token)
    )
    assert missing.status_code == 404

    restored = client.post(path, headers=_auth(admin_token), json={"confirm_tenant_id": tenant})
    assert restored.status_code == 200, restored.text
    assert restored.json()["mode"] == "IMPORT" and restored.json()["status"] == "IMPORTED"
    assert restored.json()["report"]["imported"] == before
    assert _row_counts(session_factory, tenant) == before
    again = client.get(f"/api/v1/invoices/{invoice['id']}?tenant_id={tenant}", headers=_auth(token))
    assert again.status_code == 200
    assert again.json()["official_invoice_number"] == invoice["official_invoice_number"]
    assert again.json()["items"][0]["quantity"] == invoice["items"][0]["quantity"]
    with session_factory() as db:
        balance = db.scalar(
            select(func.sum(CustomerLedgerEntry.signed_amount)).where(
                CustomerLedgerEntry.tenant_id == UUID(tenant)
            )
        )
        assert str(balance) == str(
            __import__("decimal").Decimal(invoice["net_sales"])
            - __import__("decimal").Decimal("10")
        )
        restored_tenant = db.get(Tenant, UUID(tenant))
        assert restored_tenant is not None
        floor = restored_tenant.sync_retention_floor
        high = db.execute(text("SELECT COALESCE(MAX(change_seq), 0) FROM sync_changes")).scalar()
        assert floor == high and floor > 0, "devices must re-bootstrap after an import"
    # A second import is refused: the tenant is no longer empty.
    twice = client.post(path, headers=_auth(admin_token), json={"confirm_tenant_id": tenant})
    assert twice.status_code == 409


def test_scheduled_backups_and_master_key_rotation(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "schedule")
    _business_data(client, session_factory, owner, tenant, token)
    _connect(client, tenant, token)
    settings = backup_service.get_settings()
    now = datetime(2026, 9, 18, 2, 0, tzinfo=UTC)
    with session_factory() as db:
        assert backup_service.run_due_backups(db, now, settings) == [UUID(tenant)]
        assert backup_service.run_due_backups(db, now + timedelta(hours=1), settings) == []
        kinds = list(db.scalars(select(TenantBackup.kind).order_by(TenantBackup.created_at)))
        assert kinds == ["MONTHLY"], "the first backup of a month is the monthly one"
        assert backup_service.run_due_backups(db, now + timedelta(days=1, minutes=1), settings) == [
            UUID(tenant)
        ]
        kinds = list(db.scalars(select(TenantBackup.kind).order_by(TenantBackup.created_at)))
        assert kinds == ["MONTHLY", "DAILY"]

        # KEK rotation re-wraps every tenant key and refresh token; old backups still verify.
        rotated = backup_service.rotate_master_key(db, MASTER_KEY, OTHER_KEY, "kek-test-2")
        assert rotated == 2  # one tenant key + one connection
    after = settings.model_copy(
        update={"backup_master_key": OTHER_KEY, "backup_kek_id": "kek-test-2"}
    )
    with session_factory() as db:
        first = db.scalar(select(TenantBackup).order_by(TenantBackup.created_at))
        assert first is not None
        drill = backup_service.verify_backup(db, UUID(tenant), first.id, owner.id, after)
        assert drill.status == "VERIFIED"
        assert db.scalar(select(TenantBackupConnection.kek_id)) == "kek-test-2"
