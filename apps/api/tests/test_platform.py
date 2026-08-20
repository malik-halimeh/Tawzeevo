from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.dependencies import resolve_tenant_context
from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    AuditEvent,
    SystemUserType,
    Tenant,
    TenantApplication,
    TenantMembership,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.security import hash_password

PASSWORD = "correct horse battery staple"


def create_user(
    session_factory: sessionmaker[Session], email: str, user_type: SystemUserType
) -> User:
    with session_factory() as db:
        user = User(
            first_name="Nour",
            last_name="Mansour",
            email=email,
            phone="+96170123456",
            city="Beirut",
            age=33,
            type=user_type,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def token(client: TestClient, email: str) -> str:
    response = client.post("/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def submit(
    client: TestClient, access_token: str, name: str = "Cedar Distribution"
) -> dict[str, object]:
    response = client.post(
        "/api/v1/tenant-applications",
        headers=auth(access_token),
        json={"business_name": name},
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def test_application_submission_and_platform_routes_enforce_system_roles(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    applicant = create_user(session_factory, "applicant@example.com", SystemUserType.CLIENT)
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    applicant_token = token(client, applicant.email)
    admin_token = token(client, admin.email)

    assert (
        client.post(
            "/api/v1/tenant-applications",
            headers=auth(admin_token),
            json={"business_name": "Denied"},
        ).status_code
        == 403
    )
    application = submit(client, applicant_token)
    assert application["applicant_user_id"] == str(applicant.id)
    assert application["status"] == "PENDING"
    assert (
        client.get(
            "/api/v1/platform/tenant-applications", headers=auth(applicant_token)
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/platform/tenant-applications/{application['id']}/approve",
            headers=auth(applicant_token),
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/platform/tenant-applications/{application['id']}/reject",
            headers=auth(applicant_token),
        ).status_code
        == 403
    )

    listed = client.get(
        "/api/v1/platform/tenant-applications",
        headers=auth(admin_token),
        params={"status": "PENDING", "page": 1, "limit": 1},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["total_pages"] == 1


def test_approval_is_atomic_audited_replay_safe_and_does_not_add_admin_membership(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    applicant = create_user(session_factory, "applicant@example.com", SystemUserType.CLIENT)
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    application = submit(client, token(client, applicant.email))
    admin_token = token(client, admin.email)
    access_until = date.today() + timedelta(days=30)
    grace_until = access_until + timedelta(days=7)

    response = client.post(
        f"/api/v1/platform/tenant-applications/{application['id']}/approve",
        headers=auth(admin_token),
        json={
            "access_until": str(access_until),
            "grace_until": str(grace_until),
            "review_notes": "Approved after review",
        },
    )

    assert response.status_code == 200, response.text
    approved = response.json()
    assert approved["status"] == "APPROVED"
    tenant_id = approved["tenant_id"]
    with session_factory() as db:
        tenant = db.get(Tenant, tenant_id)
        memberships = list(
            db.scalars(select(TenantMembership).where(TenantMembership.tenant_id == tenant_id))
        )
        audit = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "TENANT_APPLICATION_APPROVED")
        )
        assert tenant is not None and tenant.status is TenantStatus.ACTIVE
        assert tenant.access_until == access_until
        assert tenant.grace_until == grace_until
        assert len(memberships) == 1
        assert memberships[0].user_id == applicant.id
        assert memberships[0].role is TenantRole.OWNER
        assert all(membership.user_id != admin.id for membership in memberships)
        assert audit is not None and audit.tenant_id == tenant.id

    replay = client.post(
        f"/api/v1/platform/tenant-applications/{application['id']}/approve",
        headers=auth(admin_token),
    )
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "TENANT_APPLICATION_ALREADY_REVIEWED"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Tenant)) == 1
        assert db.scalar(select(func.count()).select_from(TenantMembership)) == 1


def test_rejection_retains_applicant_creates_no_tenant_and_is_audited(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    applicant = create_user(session_factory, "applicant@example.com", SystemUserType.CLIENT)
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    application = submit(client, token(client, applicant.email), "Rejected Business")

    response = client.post(
        f"/api/v1/platform/tenant-applications/{application['id']}/reject",
        headers=auth(token(client, admin.email)),
        json={"review_notes": "Incomplete application"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"
    assert response.json()["review_notes"] == "Incomplete application"
    with session_factory() as db:
        assert db.get(User, applicant.id) is not None
        assert db.scalar(select(func.count()).select_from(Tenant)) == 0
        assert db.scalar(select(func.count()).select_from(TenantMembership)) == 0
        audit = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "TENANT_APPLICATION_REJECTED")
        )
        assert audit is not None and audit.tenant_id is None


def test_tenant_access_list_suspend_and_reactivate_preserve_tenant_data(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    applicant = create_user(session_factory, "applicant@example.com", SystemUserType.CLIENT)
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    application = submit(client, token(client, applicant.email), "North Route")
    admin_token = token(client, admin.email)
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{application['id']}/approve",
        headers=auth(admin_token),
    )
    assert approved.status_code == 200, approved.text
    tenant_id = approved.json()["tenant_id"]

    access_until = date.today() - timedelta(days=2)
    grace_until = date.today() + timedelta(days=2)
    access_response = client.put(
        f"/api/v1/platform/tenants/{tenant_id}/access-period",
        headers=auth(admin_token),
        json={"access_until": str(access_until), "grace_until": str(grace_until)},
    )
    assert access_response.status_code == 200, access_response.text
    assert access_response.json()["access_status"] == "grace"

    listed = client.get(
        "/api/v1/platform/tenants",
        headers=auth(admin_token),
        params={"search": "NORTH", "status": "ACTIVE"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["tenants"][0]["access_status"] == "grace"

    extended_access = date.today() + timedelta(days=30)
    extended = client.put(
        f"/api/v1/platform/tenants/{tenant_id}/access-period",
        headers=auth(admin_token),
        json={"access_until": str(extended_access)},
    )
    assert extended.status_code == 200, extended.text
    assert extended.json()["access_until"] == str(extended_access)

    with session_factory() as db:
        membership = db.scalar(
            select(TenantMembership).where(TenantMembership.tenant_id == tenant_id)
        )
        assert membership is not None
        membership_id = membership.id
        tenant_created_at = db.get(Tenant, tenant_id).created_at  # type: ignore[union-attr]
        applicant_row = db.get(User, applicant.id)
        admin_row = db.get(User, admin.id)
        assert applicant_row is not None and admin_row is not None
        assert (
            str(resolve_tenant_context(db, applicant_row, membership.tenant_id).tenant.id)
            == tenant_id
        )
        with pytest.raises(AppError) as admin_denied:
            resolve_tenant_context(db, admin_row, membership.tenant_id)
        assert admin_denied.value.code == "TENANT_MEMBERSHIP_REQUIRED"

    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant_id}/suspend",
            headers=auth(token(client, applicant.email)),
        ).status_code
        == 403
    )
    suspended = client.post(
        f"/api/v1/platform/tenants/{tenant_id}/suspend",
        headers=auth(admin_token),
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "SUSPENDED"
    assert suspended.json()["suspension_reason"] == "SUBSCRIPTION_OVERDUE"
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant_id}/reactivate",
            headers=auth(token(client, applicant.email)),
        ).status_code
        == 403
    )
    with session_factory() as db:
        applicant_row = db.get(User, applicant.id)
        assert applicant_row is not None
        with pytest.raises(AppError) as suspended_access:
            resolve_tenant_context(db, applicant_row, tenant_id)
        assert suspended_access.value.code == "TENANT_SUSPENDED"

    new_access = date.today() + timedelta(days=60)
    reactivated = client.post(
        f"/api/v1/platform/tenants/{tenant_id}/reactivate",
        headers=auth(admin_token),
        json={"access_until": str(new_access), "grace_until": None},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["id"] == tenant_id
    assert reactivated.json()["status"] == "ACTIVE"
    assert reactivated.json()["access_status"] == "current"
    assert reactivated.json()["suspension_reason"] is None

    with session_factory() as db:
        tenant = db.get(Tenant, tenant_id)
        membership = db.get(TenantMembership, membership_id)
        application_row = db.get(TenantApplication, application["id"])
        assert tenant is not None and tenant.created_at == tenant_created_at
        assert membership is not None and membership.is_active is True
        assert application_row is not None and str(application_row.tenant_id) == tenant_id
        applicant_row = db.get(User, applicant.id)
        assert applicant_row is not None
        assert resolve_tenant_context(db, applicant_row, tenant.id).tenant.id == tenant.id
        actions = set(db.scalars(select(AuditEvent.action)))
        assert {
            "TENANT_APPLICATION_APPROVED",
            "TENANT_ACCESS_PERIOD_UPDATED",
            "TENANT_SUSPENDED",
            "TENANT_REACTIVATED",
        }.issubset(actions)


def test_access_period_validation_and_state_conflicts(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    applicant = create_user(session_factory, "applicant@example.com", SystemUserType.CLIENT)
    admin = create_user(session_factory, "admin@example.com", SystemUserType.ADMIN)
    application = submit(client, token(client, applicant.email))
    admin_token = token(client, admin.email)
    approved = client.post(
        f"/api/v1/platform/tenant-applications/{application['id']}/approve",
        headers=auth(admin_token),
        json={"access_until": str(date.today() + timedelta(days=10))},
    )
    tenant_id = approved.json()["tenant_id"]

    invalid_dates = client.put(
        f"/api/v1/platform/tenants/{tenant_id}/access-period",
        headers=auth(admin_token),
        json={
            "access_until": str(date.today() + timedelta(days=20)),
            "grace_until": str(date.today() + timedelta(days=19)),
        },
    )
    assert invalid_dates.status_code == 422
    shortened = client.put(
        f"/api/v1/platform/tenants/{tenant_id}/access-period",
        headers=auth(admin_token),
        json={"access_until": str(date.today() + timedelta(days=5))},
    )
    assert shortened.status_code == 409
    assert shortened.json()["detail"]["code"] == "ACCESS_PERIOD_CANNOT_BE_SHORTENED"
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant_id}/reactivate", headers=auth(admin_token)
        ).status_code
        == 409
    )

    with session_factory() as db:
        tenant = db.get(Tenant, tenant_id)
        assert tenant is not None
        tenant.status = TenantStatus.CLOSED
        tenant.closed_at = datetime.now(UTC)
        db.commit()
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant_id}/suspend", headers=auth(admin_token)
        ).status_code
        == 409
    )
