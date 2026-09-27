"""D-108: the administrator sees who applied; the applicant's own answer does not echo it."""

from __future__ import annotations

from test_invoice_editor import _auth, _login, _user

from tawzeevo_api.models import SystemUserType


def test_admin_sees_applicant_name_email_and_phone(client, session_factory):
    admin = _user(session_factory, "admin-applicant@example.com", SystemUserType.ADMIN)
    applicant = _user(session_factory, "applicant-13a@example.com", SystemUserType.CLIENT)
    token = _login(client, applicant.email)
    submitted = client.post(
        "/api/v1/tenant-applications", headers=_auth(token), json={"business_name": "Hamra Foods"}
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["applicant_email"] is None

    admin_token = _login(client, admin.email)
    listed = client.get(
        "/api/v1/platform/tenant-applications",
        headers=_auth(admin_token),
        params={"status": "PENDING"},
    )
    assert listed.status_code == 200, listed.text
    row = next(
        item for item in listed.json()["applications"] if item["id"] == submitted.json()["id"]
    )
    assert row["applicant_name"] == f"{applicant.first_name} {applicant.last_name}".strip()
    assert row["applicant_email"] == applicant.email
    assert row["applicant_phone"] == applicant.phone

    approved = client.post(
        f"/api/v1/platform/tenant-applications/{row['id']}/approve", headers=_auth(admin_token)
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["applicant_email"] == applicant.email


def test_one_click_approval_stores_thirty_days_and_no_grace(client, session_factory):
    """D-110: the quick approval is the existing approve call with access_until and no grace."""
    from datetime import date, timedelta

    admin = _user(session_factory, "admin-quick@example.com", SystemUserType.ADMIN)
    applicant = _user(session_factory, "applicant-13c@example.com", SystemUserType.CLIENT)
    submitted = client.post(
        "/api/v1/tenant-applications",
        headers=_auth(_login(client, applicant.email)),
        json={"business_name": "Quick Foods"},
    ).json()
    until = (date.today() + timedelta(days=30)).isoformat()
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{submitted['id']}/approve",
        headers=_auth(_login(client, admin.email)),
        json={"access_until": until, "grace_until": None, "review_notes": None},
    )
    assert approved.status_code == 200, approved.text
    tenants = client.get(
        "/api/v1/platform/tenants",
        headers=_auth(_login(client, admin.email)),
        params={"search": "Quick Foods"},
    ).json()["tenants"]
    assert [(row["access_until"], row["grace_until"]) for row in tenants] == [(until, None)]
