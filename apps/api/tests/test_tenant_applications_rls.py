"""Row-level security on tenant applications (audit finding TWZ-F-028; rows TWZ-A-001/A-002).

`tenant_applications` is platform-owned with a tenant link written at approval. Under a
non-bypass database role: a tenant scope sees only the application that created it, an applicant
sees and submits only their own, the platform-admin scope reviews everything, and nothing else
is readable or writable. The last test drives the real API flow under such a role so the
policies are proven compatible with the application, not only with direct SQL.
"""

from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from test_platform import auth, create_user, submit, token

from tawzeevo_api.database import get_db
from tawzeevo_api.main import app
from tawzeevo_api.models import SystemUserType


def _seed_two_approved_applications(client: TestClient, session_factory) -> dict[str, str]:
    admin = create_user(session_factory, "rls-admin@example.com", SystemUserType.ADMIN)
    applicant_a = create_user(session_factory, "rls-a@example.com", SystemUserType.CLIENT)
    applicant_b = create_user(session_factory, "rls-b@example.com", SystemUserType.CLIENT)
    app_a = submit(client, token(client, applicant_a.email), "Tenant A")
    app_b = submit(client, token(client, applicant_b.email), "Tenant B")
    admin_token = token(client, admin.email)
    tenants = {}
    for label, application in (("a", app_a), ("b", app_b)):
        approved = client.post(
            f"/api/v1/platform/tenant-applications/{application['id']}/approve",
            headers=auth(admin_token),
            json={},
        )
        assert approved.status_code == 200, approved.text
        tenants[label] = str(approved.json()["tenant_id"])
    pending = submit(client, token(client, applicant_a.email), "Second business of A")
    return {
        "application_a": str(app_a["id"]),
        "application_b": str(app_b["id"]),
        "pending_a": str(pending["id"]),
        "applicant_a": str(applicant_a.id),
        "applicant_b": str(applicant_b.id),
        "tenant_a": tenants["a"],
        "tenant_b": tenants["b"],
    }


@pytest.fixture
def rls_role(test_engine: Engine) -> Generator[str]:
    role = f"tawzeevo_app_rls_{uuid4().hex[:12]}"
    with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        admin.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        admin.exec_driver_sql(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'
        )
    try:
        yield role
    finally:
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f'DROP OWNED BY "{role}"')
            admin.exec_driver_sql(f'DROP ROLE "{role}"')


def _count_visible(connection, where: str = "", **params) -> int:
    return int(
        connection.execute(
            text(f"SELECT count(*) FROM tenant_applications {where}"), params
        ).scalar_one()
    )


def test_tenant_scope_sees_only_its_own_application_and_cannot_touch_others(
    client, session_factory, test_engine, rls_role
):
    ids = _seed_two_approved_applications(client, session_factory)
    with test_engine.connect() as connection:
        connection.exec_driver_sql(f'SET ROLE "{rls_role}"')
        connection.execute(
            text("SELECT set_config('app.current_tenant_id', :t, false)"), {"t": ids["tenant_b"]}
        )
        # Tenant B sees exactly the application that created tenant B.
        assert _count_visible(connection) == 1
        assert _count_visible(connection, "WHERE tenant_id = :a", a=ids["tenant_a"]) == 0
        assert _count_visible(connection, "WHERE id = :p", p=ids["pending_a"]) == 0
        # Writes against tenant A's row affect nothing; a tenant scope cannot review at all.
        for statement in (
            "UPDATE tenant_applications SET review_notes = 'x' WHERE tenant_id = :a",
            "DELETE FROM tenant_applications WHERE tenant_id = :a",
            "UPDATE tenant_applications SET review_notes = 'x' WHERE tenant_id = :b",
        ):
            with connection.begin_nested() as nested:
                result = connection.execute(
                    text(statement), {"a": ids["tenant_a"], "b": ids["tenant_b"]}
                )
                assert result.rowcount == 0, statement
                nested.rollback()
        connection.rollback()


def test_applicant_scope_sees_and_submits_only_own_rows(
    client, session_factory, test_engine, rls_role
):
    ids = _seed_two_approved_applications(client, session_factory)
    with test_engine.connect() as connection:
        connection.exec_driver_sql(f'SET ROLE "{rls_role}"')
        connection.execute(
            text("SELECT set_config('app.current_user_id', :u, false)"), {"u": ids["applicant_a"]}
        )
        assert _count_visible(connection) == 2  # applicant A: the approved one and the pending one
        assert _count_visible(connection, "WHERE id = :b", b=ids["application_b"]) == 0
        with connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO tenant_applications "
                    "(id, applicant_user_id, business_name, status) "
                    "VALUES (:id, :u, 'Third of A', 'PENDING')"
                ),
                {"id": uuid4(), "u": ids["applicant_a"]},
            )
        assert _count_visible(connection) == 3
        # Submitting on behalf of someone else, or pre-linked/pre-approved rows, is refused.
        for values in (
            {"id": uuid4(), "u": ids["applicant_b"], "status": "PENDING", "t": None},
            {"id": uuid4(), "u": ids["applicant_a"], "status": "APPROVED", "t": None},
            {"id": uuid4(), "u": ids["applicant_a"], "status": "PENDING", "t": ids["tenant_a"]},
        ):
            with pytest.raises(Exception, match="row-level security"), connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO tenant_applications "
                        "(id, applicant_user_id, business_name, status, tenant_id) "
                        "VALUES (:id, :u, 'x', :status, :t)"
                    ),
                    values,
                )
        # An applicant cannot review their own application.
        with connection.begin_nested() as nested:
            result = connection.execute(
                text("UPDATE tenant_applications SET status = 'APPROVED' WHERE id = :p"),
                {"p": ids["pending_a"]},
            )
            assert result.rowcount == 0
            nested.rollback()
        connection.rollback()


def test_platform_admin_scope_reviews_everything_and_no_scope_sees_nothing(
    client, session_factory, test_engine, rls_role
):
    ids = _seed_two_approved_applications(client, session_factory)
    with test_engine.connect() as connection:
        connection.exec_driver_sql(f'SET ROLE "{rls_role}"')
        assert _count_visible(connection) == 0  # no scope bound at all
        connection.execute(text("SELECT set_config('app.platform_admin', 'true', false)"))
        assert _count_visible(connection) == 3
        with connection.begin_nested() as nested:
            result = connection.execute(
                text("UPDATE tenant_applications SET review_notes = 'seen' WHERE id = :p"),
                {"p": ids["pending_a"]},
            )
            assert result.rowcount == 1
            nested.rollback()
        connection.rollback()


def test_application_lifecycle_works_under_a_non_bypass_database_role(
    client, session_factory, test_engine
):
    """The real API (submit -> list -> approve -> reject) under a NOBYPASSRLS login role: proves the
    policies are compatible with every application path, not just with direct SQL probes."""
    role = f"tawzeevo_app_login_{uuid4().hex[:12]}"
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
    rls_engine = create_engine(
        test_engine.url.set(username=role, password=secret), pool_pre_ping=True
    )
    rls_sessions = sessionmaker(bind=rls_engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session]:
        with rls_sessions() as session:
            yield session

    try:
        with rls_engine.connect() as probe:
            assert (
                probe.execute(
                    text(
                        "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
                    )
                ).scalar_one()
                is False
            )
        admin_user = create_user(session_factory, "rls-api-admin@example.com", SystemUserType.ADMIN)
        applicant = create_user(
            session_factory, "rls-api-client@example.com", SystemUserType.CLIENT
        )
        other = create_user(session_factory, "rls-api-other@example.com", SystemUserType.CLIENT)
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, base_url="https://testserver") as rls_client:
            applicant_token = token(rls_client, applicant.email)
            first = submit(rls_client, applicant_token, "Cedar Van")
            second = submit(rls_client, token(rls_client, other.email), "Other Van")
            admin_token = token(rls_client, admin_user.email)
            listed = rls_client.get(
                "/api/v1/platform/tenant-applications", headers=auth(admin_token)
            )
            assert listed.status_code == 200, listed.text
            assert {item["id"] for item in listed.json()["applications"]} == {
                first["id"],
                second["id"],
            }
            approved = rls_client.post(
                f"/api/v1/platform/tenant-applications/{first['id']}/approve",
                headers=auth(admin_token),
                json={},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "APPROVED" and approved.json()["tenant_id"]
            rejected = rls_client.post(
                f"/api/v1/platform/tenant-applications/{second['id']}/reject",
                headers=auth(admin_token),
                json={"review_notes": "not now"},
            )
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["status"] == "REJECTED"
            again = rls_client.get(
                "/api/v1/platform/tenant-applications?status=APPROVED", headers=auth(admin_token)
            )
            assert [item["id"] for item in again.json()["applications"]] == [first["id"]]
            # A client (non-admin) still cannot list applications through the API.
            assert (
                rls_client.get(
                    "/api/v1/platform/tenant-applications", headers=auth(applicant_token)
                ).status_code
                == 403
            )
    finally:
        app.dependency_overrides.clear()
        rls_engine.dispose()
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f'DROP OWNED BY "{role}"')
            admin.exec_driver_sql(f'DROP ROLE "{role}"')
