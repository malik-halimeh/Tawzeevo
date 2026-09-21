"""Phase 9 P9-M1 (PHASE_09.md B/C, D-077): password recovery with hashed single-use tokens,
enumeration-safe answers, session invalidation, audit without secrets; login and recovery abuse
controls; the mail adapter never fakes success."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_auth import login, register

from tawzeevo_api.models import AuditEvent, PasswordResetToken
from tawzeevo_api.routes import auth as auth_routes
from tawzeevo_api.services import mailer
from tawzeevo_api.services.mailer import MailerError, memory_outbox


@pytest.fixture(autouse=True)
def _fresh_limiters():
    auth_routes.reset_auth_limiters()
    memory_outbox().clear()
    yield
    auth_routes.reset_auth_limiters()


def _link_token(text: str) -> str:
    match = re.search(r"/reset-password#([A-Za-z0-9_-]+)", text)
    assert match, text
    return match.group(1)


def test_forgot_reset_invalidates_sessions_and_leaks_nothing(client, session_factory):
    register(client)
    first = login(client)
    headers = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.get("/users/me", headers=headers).status_code == 200

    # Unknown and known addresses get the same answer; only the known one produces a mail.
    unknown = client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    assert unknown.status_code == 202 and unknown.json() == {"status": "accepted"}
    assert memory_outbox() == []
    known = client.post(
        "/api/v1/auth/password/forgot", json={"email": " Layla.Haddad@example.com "}
    )
    assert known.status_code == 202 and known.json() == unknown.json()
    assert len(memory_outbox()) == 1 and memory_outbox()[0].to == "layla.haddad@example.com"
    token = _link_token(memory_outbox()[0].text)
    assert "reset-password#" in memory_outbox()[0].text  # fragment, never a query string

    # Stored as a hash only; audit rows never carry the token or the address.
    with session_factory() as db:
        rows = db.scalars(select(PasswordResetToken)).all()
        assert len(rows) == 1 and rows[0].token_sha256 != token and len(rows[0].token_sha256) == 64
        assert rows[0].used_at is None
        assert (
            timedelta(minutes=29) < rows[0].expires_at - datetime.now(UTC) <= timedelta(minutes=30)
        )
        audit = db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("password_reset%"))
        ).all()
        assert [event.action for event in audit] == ["password_reset_requested"]
        assert token not in str([event.details for event in audit])
        assert "example.com" not in str([event.details for event in audit])

    # A second request supersedes the first link.
    client.post("/api/v1/auth/password/forgot", json={"email": "layla.haddad@example.com"})
    newest = _link_token(memory_outbox()[1].text)
    stale = client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "another strong one"}
    )
    assert stale.status_code == 400 and stale.json()["detail"]["code"] == "RESET_TOKEN_INVALID"

    # Weak passwords are refused before anything is touched.
    weak = client.post("/api/v1/auth/password/reset", json={"token": newest, "password": "short"})
    assert weak.status_code == 422

    # The reset succeeds once, clears the refresh cookie, kills every session and access token.
    done = client.post(
        "/api/v1/auth/password/reset", json={"token": newest, "password": "brand new passphrase"}
    )
    assert done.status_code == 204, done.text
    assert "tawzeevo_refresh_token=" in done.headers.get("set-cookie", "")
    again = client.post(
        "/api/v1/auth/password/reset", json={"token": newest, "password": "brand new passphrase"}
    )
    assert again.status_code == 400  # single use
    assert client.get("/users/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/login",
            json={"email": "layla.haddad@example.com", "password": "correct horse battery staple"},
        ).status_code
        == 401
    )
    login(client, password="brand new passphrase")
    with session_factory() as db:
        audit = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "password_reset_completed")
        ).all()
        assert len(audit) == 1 and audit[0].details == {"sessions_revoked": True}


def test_expired_and_garbage_tokens_are_refused(client, session_factory):
    register(client)
    client.post("/api/v1/auth/password/forgot", json={"email": "layla.haddad@example.com"})
    token = _link_token(memory_outbox()[0].text)
    with session_factory() as db:
        row = db.scalars(select(PasswordResetToken)).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    expired = client.post(
        "/api/v1/auth/password/reset", json={"token": token, "password": "brand new passphrase"}
    )
    assert expired.status_code == 400
    garbage = client.post(
        "/api/v1/auth/password/reset", json={"token": "x" * 40, "password": "brand new passphrase"}
    )
    assert garbage.status_code == 400
    assert (
        client.post(
            "/login",
            json={"email": "layla.haddad@example.com", "password": "correct horse battery staple"},
        ).status_code
        == 200
    )


def test_login_brute_force_and_recovery_request_throttles(client):
    register(client)
    bad = {"email": "layla.haddad@example.com", "password": "wrong password here"}
    codes = [client.post("/login", json=bad).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    good = {"email": "layla.haddad@example.com", "password": "correct horse battery staple"}
    assert client.post("/login", json=good).status_code == 429  # the window applies to the client
    auth_routes.reset_auth_limiters()
    assert client.post("/login", json=good).status_code == 200  # success clears the failures
    assert client.post("/login", json=bad).status_code == 401

    auth_routes.reset_auth_limiters()
    forgot = [
        client.post("/api/v1/auth/password/forgot", json={"email": f"u{i}@example.com"}).status_code
        for i in range(11)
    ]
    assert forgot == [202] * 10 + [429]
    blocked = client.post(
        "/api/v1/auth/password/reset", json={"token": "y" * 40, "password": "brand new passphrase"}
    )
    assert blocked.status_code == 429  # reset attempts share the recovery budget


def test_mail_provider_failure_is_counted_but_the_answer_stays_enumeration_safe(
    client, monkeypatch
):
    """D-077: a provider outage must not turn the forgot endpoint into an account oracle. Known
    and unknown addresses get the same 202; the failure is counted for the alert probe."""
    from tawzeevo_api import metrics

    register(client)

    class Broken:
        def send(self, mail):
            raise MailerError("down")

    monkeypatch.setattr(mailer, "get_mailer", lambda settings=None: Broken())
    monkeypatch.setattr(
        "tawzeevo_api.services.password_reset.get_mailer", lambda settings=None: Broken()
    )
    metrics.reset_for_tests()
    known = client.post("/api/v1/auth/password/forgot", json={"email": "layla.haddad@example.com"})
    unknown = client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert metrics.snapshot()["mail_failures"] == 1  # the outage is observable, not the address
    assert memory_outbox() == []


def test_brevo_adapter_sends_the_expected_payload(monkeypatch):
    calls: list[dict[str, object]] = []

    class Response:
        status_code = 201

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json})
        return Response()

    monkeypatch.setattr(mailer.httpx, "post", fake_post)
    adapter = mailer.BrevoMailer(api_key="xkeysib-test", sender="Tawzeevo <no-reply@example.com>")
    adapter.send(mailer.Mail(to="x@example.com", subject="s", text="t"))
    assert calls[0]["url"] == "https://api.brevo.com/v3/smtp/email"
    assert calls[0]["headers"]["api-key"] == "xkeysib-test"
    assert calls[0]["json"] == {
        "sender": {"name": "Tawzeevo", "email": "no-reply@example.com"},
        "to": [{"email": "x@example.com"}],
        "subject": "s",
        "textContent": "t",
    }
    Response.status_code = 401
    with pytest.raises(MailerError):
        adapter.send(mailer.Mail(to="x@example.com", subject="s", text="t"))
