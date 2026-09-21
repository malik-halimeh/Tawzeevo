"""Phase 9 P9-M3 (PHASE_09.md G): request correlation, structured access log without secrets,
health with the migration head."""

from __future__ import annotations

import json
import logging
import re


def test_request_id_is_echoed_or_generated_and_errors_carry_it(client):
    generated = client.get("/health")
    assert re.fullmatch(r"[0-9a-f]{32}", generated.headers["x-request-id"])
    echoed = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    assert echoed.headers["x-request-id"] == "trace-abc-12345"
    hostile = client.get("/health", headers={"X-Request-ID": "x" * 200 + "\r\nInjected: 1"})
    assert re.fullmatch(r"[0-9a-f]{32}", hostile.headers["x-request-id"])  # never reflected
    # Error bodies stay constant (public failure responses are compared byte for byte); the id
    # travels in the header only.
    denied = client.get("/users/me", headers={"X-Request-ID": "trace-denied-1"})
    assert denied.status_code == 401 and denied.headers["x-request-id"] == "trace-denied-1"
    assert "request_id" not in denied.text


def test_access_log_has_route_template_and_no_query_or_secret(client, caplog, monkeypatch):
    # Alembic's fileConfig disables unrelated loggers during earlier migration tests.
    logger = logging.getLogger("tawzeevo.access")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)
    caplog.set_level(logging.INFO, logger="tawzeevo.access")
    secret = "a" * 32 + "." + "b" * 43
    client.get(
        "/api/v1/public/invoice/data?debug=1",
        headers={"X-Invoice-Capability": secret, "X-Request-ID": "trace-log-1"},
    )
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "tawzeevo.access"]
    entry = next(line for line in lines if line["request_id"] == "trace-log-1")
    assert entry["route"] == "/api/v1/public/invoice/data" and entry["status"] == 404
    assert entry["method"] == "GET" and entry["duration_ms"] >= 0
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert secret not in joined and "debug=1" not in joined
    assert not any(line["route"] == "/health" for line in lines)  # probes stay quiet


def test_database_health_reports_the_migration_head(client):
    body = client.get("/health/database").json()
    assert body["status"] == "ok" and body["migration_head"] == "20260921_0030"


def test_health_metrics_counts_without_content(client):
    from tawzeevo_api import metrics

    metrics.reset_for_tests()
    client.get("/health")
    client.post("/login", json={"email": "nobody@example.com", "password": "wrong password"})
    body = client.get("/health/metrics").json()
    assert body["http_responses_total"] >= 2 and body["auth_login_failures"] == 1
    assert body["http_responses_5xx"] == 0 and body["http_5xx_ratio"] == 0.0
    assert set(body) >= {
        "uptime_seconds",
        "sync_push_rejected",
        "backup_failures",
        "mail_failures",
        "auth_login_throttled",
    }
    assert "nobody@example.com" not in str(body)


def test_uvicorn_access_log_never_records_query_strings(caplog):
    """TWZ-A-058: the raw request line uvicorn logs is stripped of its query string (tenant and
    device ids, cursors, filters, anything a client put in the URL) while the path is kept."""
    import logging

    from tawzeevo_api.public_invoice_security import install_capability_log_redaction

    install_capability_log_redaction()
    access = logging.getLogger("uvicorn.access")
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        access.info(
            '%s - "%s %s HTTP/%s" %d',
            "10.0.0.7:1234",
            "GET",
            "/api/v1/sync/pull?tenant_id=abc&device_installation_id=def&cursor=0&secret=x",
            "1.1",
            200,
        )
    rendered = caplog.records[-1].getMessage()
    assert '"GET /api/v1/sync/pull HTTP/1.1" 200' in rendered
    assert "?" not in rendered and "tenant_id" not in rendered and "secret" not in rendered
