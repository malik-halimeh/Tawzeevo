"""D-111: my applications, one pending per person, and the approval email (best effort)."""

from __future__ import annotations

from test_invoice_editor import _auth, _login, _user

from tawzeevo_api.models import SystemUserType
from tawzeevo_api.services import mailer, platform
from tawzeevo_api.services.mailer import memory_outbox


def test_mine_one_pending_and_approval_email(client, session_factory):
    admin = _user(session_factory, "admin-mine@example.com", SystemUserType.ADMIN)
    applicant = _user(session_factory, "applicant-mine@example.com", SystemUserType.CLIENT)
    other = _user(session_factory, "other-mine@example.com", SystemUserType.CLIENT)
    token = _login(client, applicant.email)
    assert client.get("/api/v1/tenant-applications/mine", headers=_auth(token)).json() == []

    first = client.post(
        "/api/v1/tenant-applications", headers=_auth(token), json={"business_name": "Mine Foods"}
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/tenant-applications", headers=_auth(token), json={"business_name": "Mine Two"}
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "APPLICATION_ALREADY_PENDING"

    mine = client.get("/api/v1/tenant-applications/mine", headers=_auth(token)).json()
    assert [(row["business_name"], row["status"]) for row in mine] == [("Mine Foods", "PENDING")]
    # Another person sees only their own (none).
    other_token = _login(client, other.email)
    assert client.get("/api/v1/tenant-applications/mine", headers=_auth(other_token)).json() == []
    assert client.get("/api/v1/tenant-applications/mine").status_code == 401

    before = len(memory_outbox())
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{first.json()['id']}/approve",
        headers=_auth(_login(client, admin.email)),
    )
    assert approved.status_code == 200, approved.text
    sent = memory_outbox()[before:]
    assert [mail.to for mail in sent] == [applicant.email]
    assert "Mine Foods" in sent[0].subject
    mine = client.get("/api/v1/tenant-applications/mine", headers=_auth(token)).json()
    assert mine[0]["status"] == "APPROVED"
    # After approval a new application may be sent again.
    again = client.post(
        "/api/v1/tenant-applications", headers=_auth(token), json={"business_name": "Mine Two"}
    )
    assert again.status_code == 201, again.text


def test_approval_stands_when_the_email_fails(client, session_factory, monkeypatch):
    class Broken:
        def send(self, _mail: mailer.Mail) -> None:
            raise mailer.MailerError("provider down")

    monkeypatch.setattr(platform, "get_mailer", lambda: Broken())
    admin = _user(session_factory, "admin-mine2@example.com", SystemUserType.ADMIN)
    applicant = _user(session_factory, "applicant-mine2@example.com", SystemUserType.CLIENT)
    created = client.post(
        "/api/v1/tenant-applications",
        headers=_auth(_login(client, applicant.email)),
        json={"business_name": "Quiet Mail"},
    ).json()
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{created['id']}/approve",
        headers=_auth(_login(client, admin.email)),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
