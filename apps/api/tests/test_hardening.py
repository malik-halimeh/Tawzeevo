from __future__ import annotations

import json
from collections.abc import Mapping
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from tawzeevo_api.models import Customer, SystemUserType, Tenant, User
from tawzeevo_api.security import hash_password

PASSWORD = "correct horse battery staple"
PROTECTED_REQUESTS: tuple[tuple[str, str, Mapping[str, object] | None], ...] = (
    ("GET", "/users/me", None),
    ("PUT", "/users/me", {"city": "Beirut"}),
    ("GET", "/users", None),
    ("POST", "/users", None),
    ("PUT", "/users/00000000-0000-0000-0000-000000000001", {"city": "Beirut"}),
    ("DELETE", "/users/00000000-0000-0000-0000-000000000001", None),
    ("POST", "/api/v1/tenant-applications", {"business_name": "Denied"}),
    ("GET", "/api/v1/platform/tenant-applications", None),
    (
        "POST",
        "/api/v1/platform/tenant-applications/00000000-0000-0000-0000-000000000001/approve",
        {},
    ),
    (
        "POST",
        "/api/v1/platform/tenant-applications/00000000-0000-0000-0000-000000000001/reject",
        {},
    ),
    ("GET", "/api/v1/platform/tenants", None),
    (
        "PUT",
        "/api/v1/platform/tenants/00000000-0000-0000-0000-000000000001/access-period",
        {"access_until": "2026-12-31"},
    ),
    (
        "POST",
        "/api/v1/platform/tenants/00000000-0000-0000-0000-000000000001/suspend",
        {},
    ),
    (
        "POST",
        "/api/v1/platform/tenants/00000000-0000-0000-0000-000000000001/reactivate",
        {},
    ),
    (
        "GET",
        "/api/v1/tenants/00000000-0000-0000-0000-000000000001/categories",
        None,
    ),
)


def create_client_user(session_factory: sessionmaker[Session]) -> User:
    with session_factory() as db:
        user = User(
            first_name="Negative",
            last_name="Authorization",
            email="negative.auth@example.com",
            phone="+96170123456",
            city="Beirut",
            age=31,
            type=SystemUserType.CLIENT,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


@pytest.mark.parametrize(("method", "path", "payload"), PROTECTED_REQUESTS)
def test_every_phase1_protected_surface_rejects_unauthenticated_requests(
    client: TestClient,
    method: str,
    path: str,
    payload: Mapping[str, object] | None,
) -> None:
    response = client.request(method, path, json=payload)

    assert response.status_code == 401, response.text
    assert response.json()["detail"]["code"] == "INVALID_AUTHENTICATION"


def test_client_is_denied_all_platform_admin_and_unowned_tenant_surfaces(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    user = create_client_user(session_factory)
    login = client.post("/login", json={"email": user.email, "password": PASSWORD})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    denied_requests = [request for request in PROTECTED_REQUESTS if "/platform/" in request[1]]
    denied_requests.append(
        (
            "GET",
            "/api/v1/tenants/00000000-0000-0000-0000-000000000001/categories",
            None,
        )
    )

    for method, path, payload in denied_requests:
        response = client.request(method, path, headers=headers, json=payload)
        assert response.status_code == 403, f"{method} {path}: {response.text}"


def test_openapi_has_complete_unique_phase1_contract(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    expected_root_methods = {
        "/register": "post",
        "/login": "post",
        "/users": "get",
        "/users/me": "get",
        "/users/{user_id}": "put",
        "/stats/count": "get",
        "/stats/average-age": "get",
        "/stats/top-cities": "get",
    }
    for path, method in expected_root_methods.items():
        assert method in document["paths"][path]
    assert "post" in document["paths"]["/users"]
    assert "put" in document["paths"]["/users/me"]
    assert "delete" in document["paths"]["/users/{user_id}"]

    operations = [
        operation
        for path_item in document["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    operation_ids = [operation["operationId"] for operation in operations]
    assert len(operation_ids) == len(set(operation_ids))
    assert "password_hash" not in json.dumps(document)
    assert {tag["name"] for tag in document["tags"]} >= {
        "authentication",
        "users",
        "public statistics",
        "tenant applications",
        "platform administration",
        "tenant operations",
    }


@pytest.mark.integration
def test_migrations_build_a_new_database_from_zero(test_engine: Engine) -> None:
    database_name = f"tawzeevo_zero_{uuid4().hex[:12]}"
    admin_engine = create_engine(
        test_engine.url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    target_url = test_engine.url.set(database=database_name)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    config_path = __file__.replace("tests\\test_hardening.py", "alembic.ini")
    config = Config(config_path)
    config.set_main_option(
        "sqlalchemy.url",
        target_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        command.upgrade(config, "head")
        with target_engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == ("20260820_0003")
        assert {
            "users",
            "auth_sessions",
            "tenants",
            "tenant_memberships",
            "tenant_applications",
            "audit_events",
            "customers",
            "categories",
            "tenant_products",
            "invoices",
            "invoice_items",
        }.issubset(inspect(target_engine).get_table_names())
    finally:
        target_engine.dispose()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
        admin_engine.dispose()


@pytest.mark.integration
def test_postgresql_rls_enforces_tenant_visibility_and_write_checks(
    test_engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    role_name = f"tawzeevo_rls_{uuid4().hex}"
    with session_factory() as db:
        first_tenant = Tenant(name="First tenant")
        second_tenant = Tenant(name="Second tenant")
        db.add_all([first_tenant, second_tenant])
        db.flush()
        first_customer = Customer(
            tenant_id=first_tenant.id,
            name="Visible customer",
            phone="+96170111111",
        )
        second_customer = Customer(
            tenant_id=second_tenant.id,
            name="Hidden customer",
            phone="+96170222222",
        )
        db.add_all([first_customer, second_customer])
        db.commit()
        first_tenant_id = first_tenant.id
        second_tenant_id = second_tenant.id
        first_customer_id = first_customer.id

    with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        can_create_roles = admin.execute(
            text("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()
        assert can_create_roles, "RLS integration tests require a disposable PostgreSQL owner role"
        admin.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        admin.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
        admin.exec_driver_sql(f'GRANT SELECT, INSERT ON customers TO "{role_name}"')

    connection = test_engine.connect()
    try:
        with connection.begin():
            connection.exec_driver_sql(f'SET ROLE "{role_name}"')
            connection.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": str(first_tenant_id)},
            )
            visible_ids = set(connection.execute(select(Customer.id)).scalars())
            assert visible_ids == {first_customer_id}
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO customers (id, tenant_id, name, phone) "
                        "VALUES (:id, :tenant_id, :name, :phone)"
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": second_tenant_id,
                        "name": "Blocked cross-tenant write",
                        "phone": "+96170333333",
                    },
                )
        connection.exec_driver_sql("RESET ROLE")
        connection.commit()
    finally:
        if connection.in_transaction():
            connection.rollback()
        connection.close()
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
            admin.exec_driver_sql(f'DROP ROLE "{role_name}"')
