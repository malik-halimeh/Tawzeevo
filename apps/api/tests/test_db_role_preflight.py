"""Database-role preflight (audit finding TWZ-F-002): the API reports whether the role it connects
with is subject to row-level security and can refuse to start otherwise. The hosted role itself
can only be checked by the owner on the hosted database; these tests prove the local mechanism."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tawzeevo_api.db_role import check_database_role, inspect_database_role


def test_superuser_test_role_is_reported_as_bypassing_rls(session_factory, caplog):
    with session_factory() as db:
        role = inspect_database_role(db)
        assert role.name and (role.superuser or role.bypass_rls)
        assert role.rls_enforced is False
        with caplog.at_level("WARNING", logger="tawzeevo.database"):
            returned = check_database_role(db, require_rls_subject=False)
        assert returned == role
        assert any("bypasses row-level security" in r.message for r in caplog.records)
        with pytest.raises(RuntimeError, match="DB_ROLE_REQUIRE_RLS_SUBJECT"):
            check_database_role(db, require_rls_subject=True)


def test_rls_subject_role_passes_the_preflight_even_when_required(test_engine: Engine):
    role_name = f"tawzeevo_preflight_{uuid4().hex[:12]}"
    with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
    try:
        with test_engine.connect() as connection:
            connection.exec_driver_sql(f'SET ROLE "{role_name}"')
            with Session(bind=connection) as db:
                role = inspect_database_role(db)
                assert role.name == role_name and role.rls_enforced is True
                assert check_database_role(db, require_rls_subject=True) == role
            connection.exec_driver_sql("RESET ROLE")
            connection.rollback()
    finally:
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f'DROP ROLE "{role_name}"')


def test_database_health_reports_the_role_flag_without_names(client, test_engine: Engine):
    body = client.get("/health/database").json()
    assert body["status"] == "ok"
    with test_engine.connect() as connection:
        expected = not connection.execute(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()
    assert body["database_role_rls_enforced"] is expected
    assert "rolname" not in body and "role_name" not in body


def test_health_check_still_answers_ok_first_for_the_deploy_gate(client):
    # deploy.yml greps the raw body for '"status":"ok"' before comparing the migration head.
    assert client.get("/health/database").text.startswith('{"status":"ok"')
