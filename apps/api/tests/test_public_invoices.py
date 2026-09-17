import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker
from test_invoice_editor import (
    _attach_latest_cost,
    _auth,
    _catalog,
    _confirmable_payload,
    _login,
    _owner_context,
)

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    PublicInvoiceCapability,
    Tenant,
    TenantMembership,
    TenantRole,
    TenantStatus,
)
from tawzeevo_api.public_invoice_security import CapabilityLogFilter, PublicInvoiceRateLimiter
from tawzeevo_api.repositories.tenancy import set_tenant_scope
from tawzeevo_api.services.public_invoices import issue_capability, resolve_public_invoice


def _invoice(client: TestClient, session_factory: sessionmaker[Session], suffix: str = "public"):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _, product, customer = _catalog(client, tenant, token)
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    payload = _confirmable_payload(customer["id"], product["id"])
    response = client.post(
        f"/api/v1/invoices?tenant_id={tenant}", headers=_auth(token), json=payload
    )
    assert response.status_code == 201, response.text
    # D-042: only a confirmed invoice can be shared, so the fixture confirms it first.
    confirmed = client.post(
        f"/api/v1/invoices/{response.json()['id']}/confirm?tenant_id={tenant}",
        headers=_auth(token),
        json={"expected_revision_id": response.json()["current_revision_id"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    invoice = confirmed.json()
    path = f"/api/v1/invoices/{invoice['id']}/capabilities"
    issued = client.post(f"{path}?tenant_id={tenant}", headers=_auth(token))
    assert issued.status_code == 201, issued.text
    return owner, tenant, token, invoice, payload, path, issued.json()


def _resolve(client: TestClient, issued: dict):
    return client.get(
        "/api/v1/public/invoice/data",
        headers={"X-Invoice-Capability": issued["public_path"].split("#")[1]},
    )


def _privacy(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_capability_projection_current_revision_privacy_and_no_stored_secret(
    client, session_factory
):
    _, tenant, auth, invoice, payload, path, issued = _invoice(client, session_factory)
    raw = issued["public_path"].split("#")[1]
    assert len(raw.split(".")[1]) == 43
    assert issued["customer_phone"] == "+96170123456"
    assert "net_sales" not in issued["summary"]  # Human summary, no owner object serialization.
    with session_factory() as db:
        cap = db.get(PublicInvoiceCapability, UUID(issued["id"]))
        assert cap.token_sha256 == hashlib.sha256(raw.encode()).hexdigest()
        assert timedelta(days=89) < cap.expires_at - datetime.now(UTC) <= timedelta(days=90)
        assert raw not in str([event.details for event in db.scalars(select(AuditEvent))])
    response = _resolve(client, issued)
    assert response.status_code == 200, response.text
    _privacy(response)
    public = response.json()
    assert set(public) == {
        "business_name",
        "customer_name",
        "status",
        "number",
        "revision",
        "currency",
        "subtotal",
        "discount",
        "markup",
        "net_sales",
        "items",
    }
    assert set(public["items"][0]) == {
        "name",
        "barcode",
        "quantity",
        "unit",
        "pieces_per_box",
        "unit_price",
        "discount",
        "markup",
        "total",
    }
    for secret_field in (
        "prior_balance",
        "total_due",
        "grade",
        "supplier",
        "cost",
        "profit",
        "customer_id",
        "tenant_id",
        "latitude",
        "phone",
        "history",
    ):
        assert secret_field not in response.text
    assert public["net_sales"] == invoice["net_sales"]
    payload["client_command_id"] = str(uuid4())
    payload["expected_predecessor_revision_id"] = invoice["current_revision_id"]
    payload["invoice_markup_expression"] = "2"
    edited = client.put(
        f"/api/v1/invoices/{invoice['id']}?tenant_id={tenant}", headers=_auth(auth), json=payload
    )
    assert edited.status_code == 200, edited.text
    assert _resolve(client, issued).json()["net_sales"] == edited.json()["net_sales"]
    listed = client.get(f"{path}?tenant_id={tenant}", headers=_auth(auth))
    _privacy(listed)
    assert raw not in listed.text and "public_path" not in listed.text
    shell = client.get("/api/v1/public/invoice")
    _privacy(shell)
    assert "script-src 'sha256-" in shell.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in shell.headers["content-security-policy"]
    assert "history.replaceState" in shell.text


def test_capability_rotation_expiry_revocation_and_uniform_invalid_access(client, session_factory):
    _, tenant, auth, invoice, _, path, issued = _invoice(client, session_factory, "lifecycle")
    for invalid in ("", invoice["id"], tenant, "wrong", issued["public_path"].split("#")[1][:-1]):
        response = client.get(
            "/api/v1/public/invoice/data", headers={"X-Invoice-Capability": invalid}
        )
        assert response.status_code == 404
        _privacy(response)
        assert response.json()["detail"]["code"] == "PUBLIC_INVOICE_UNAVAILABLE"
    rotated = client.post(f"{path}/{issued['id']}/rotate?tenant_id={tenant}", headers=_auth(auth))
    assert rotated.status_code == 201, rotated.text
    assert _resolve(client, issued).status_code == 404
    replacement = rotated.json()
    assert _resolve(client, replacement).status_code == 200
    assert (
        client.post(
            f"{path}/{issued['id']}/rotate?tenant_id={tenant}", headers=_auth(auth)
        ).status_code
        == 409
    )
    with session_factory() as db:
        cap = db.get(PublicInvoiceCapability, UUID(replacement["id"]))
        cap.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert _resolve(client, replacement).status_code == 404
    for _ in range(2):
        assert (
            client.delete(
                f"{path}/{replacement['id']}?tenant_id={tenant}", headers=_auth(auth)
            ).status_code
            == 204
        )
    assert _resolve(client, replacement).status_code == 404


def test_capability_owner_authority_tenant_hint_and_suspension(client, session_factory):
    owner, tenant, auth, invoice, _, path, issued = _invoice(client, session_factory, "authority")
    other, second, other_auth = _owner_context(client, session_factory, "other-public")
    assert client.post(f"{path}?tenant_id={tenant}", headers=_auth(other_auth)).status_code == 403
    assert client.post(f"{path}?tenant_id={second}", headers=_auth(other_auth)).status_code == 404
    admin_auth = _login(client, "admin-authority@example.com")
    assert client.post(f"{path}?tenant_id={tenant}", headers=_auth(admin_auth)).status_code == 403
    raw = issued["public_path"].split("#")[1]
    forged = UUID(second).hex + raw[32:]
    assert (
        client.get(
            "/api/v1/public/invoice/data", headers={"X-Invoice-Capability": forged}
        ).status_code
        == 404
    )
    with session_factory() as db:
        db.add(TenantMembership(tenant_id=tenant, user_id=other.id, role=TenantRole.DRIVER))
        db.commit()
    assert client.post(f"{path}?tenant_id={tenant}", headers=_auth(other_auth)).status_code == 403
    with session_factory() as db:
        t = db.get(Tenant, UUID(tenant))
        t.status = TenantStatus.SUSPENDED
        db.commit()
    assert _resolve(client, issued).status_code == 404
    with session_factory() as db:
        t = db.get(Tenant, UUID(tenant))
        t.status = TenantStatus.ACTIVE
        db.commit()
    assert _resolve(client, issued).status_code == 200


def test_capability_rotation_is_serialized(client, session_factory):
    owner, tenant, _, invoice, _, _, issued = _invoice(client, session_factory, "rotate-race")

    def rotate():
        with session_factory() as db:
            set_tenant_scope(db, UUID(tenant))
            try:
                issue_capability(
                    db, UUID(tenant), owner.id, UUID(invoice["id"]), rotate_id=UUID(issued["id"])
                )
                return 201
            except AppError as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: rotate(), range(2))) == [201, 409]
    with session_factory() as db:
        assert (
            len(
                list(
                    db.scalars(
                        select(PublicInvoiceCapability).where(
                            PublicInvoiceCapability.rotated_from_id == UUID(issued["id"]),
                        )
                    )
                )
            )
            == 1
        )


def test_public_capability_resolves_under_forced_rls_without_bypass(
    client, session_factory, test_engine: Engine
):
    _, tenant, _, _, _, _, issued = _invoice(client, session_factory, "public-rls")
    role = f"tawzeevo_public_test_{uuid4().hex}"
    with test_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        connection.exec_driver_sql(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{role}"')
    try:
        with test_engine.connect() as connection:
            connection.exec_driver_sql(f'SET ROLE "{role}"')
            with Session(bind=connection) as db:
                assert list(db.scalars(select(PublicInvoiceCapability))) == []
                assert resolve_public_invoice(db, issued["public_path"].split("#")[1]).business_name
                set_tenant_scope(db, uuid4())
                assert list(db.scalars(select(PublicInvoiceCapability))) == []
            connection.rollback()
    finally:
        with test_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP OWNED BY "{role}"')
            connection.exec_driver_sql(f'DROP ROLE "{role}"')


def test_public_rate_limit_and_access_log_redaction(client, monkeypatch, caplog):
    limiter = PublicInvoiceRateLimiter(limit=2, max_clients=1)
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a") and not limiter.allow("b")
    monkeypatch.setattr(PublicInvoiceRateLimiter, "allow", lambda self, address: False)
    response = client.get("/api/v1/public/invoice/data")
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
    _privacy(response)
    raw = "a" * 32 + "." + "B" * 43
    # Alembic's fileConfig disables unrelated loggers during earlier migration tests.
    # Restore this test's capture surface without changing production logging policy.
    logger = logging.getLogger("uvicorn.access")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        logger.info("GET /wrong?token=%s", raw)
    assert raw not in caplog.text and "[invoice-link-redacted]" in caplog.text
    record = logging.LogRecord("test", logging.INFO, "", 1, "value %s", (raw,), None)
    assert CapabilityLogFilter().filter(record)
    assert raw not in record.getMessage()


def test_public_unexpected_failure_is_private_and_does_not_log_token(client, monkeypatch, caplog):
    raw = "a" * 32 + "." + "B" * 43
    logger = logging.getLogger("tawzeevo.public_invoices")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)

    def fail(db, token):
        raise RuntimeError(token)

    monkeypatch.setattr("tawzeevo_api.routes.public_invoices.resolve_public_invoice", fail)
    response = client.get("/api/v1/public/invoice/data", headers={"X-Invoice-Capability": raw})
    assert response.status_code == 503
    _privacy(response)
    assert raw not in response.text and raw not in caplog.text
    assert "Public invoice request failed" in caplog.text
