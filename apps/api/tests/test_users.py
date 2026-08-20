from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.errors import AppError
from tawzeevo_api.models import (
    SystemUserType,
    Tenant,
    TenantMembership,
    TenantRole,
    TenantStatus,
    User,
)
from tawzeevo_api.security import hash_password
from tawzeevo_api.services.users import soft_delete_user

PASSWORD = "correct horse battery staple"


def create_user(
    session_factory: sessionmaker[Session],
    *,
    email: str,
    user_type: SystemUserType,
    first_name: str = "Layla",
    last_name: str = "Haddad",
    city: str = "Beirut",
    age: int = 31,
) -> User:
    with session_factory() as db:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone="+96170123456",
            phone_raw="+961 70 123 456",
            city=city,
            age=age,
            type=user_type,
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def access_token(client: TestClient, email: str, password: str = PASSWORD) -> str:
    response = client.post("/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def user_payload(email: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Maya",
        "last_name": "Khoury",
        "email": email,
        "phone": "+96171111222",
        "city": "Byblos",
        "age": 28,
        "password": PASSWORD,
        "type": "client",
    }
    payload.update(overrides)
    return payload


def test_profile_is_safe_and_user_can_update_profile_and_password(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    user = create_user(session_factory, email="layla@example.com", user_type=SystemUserType.CLIENT)
    token = access_token(client, user.email)

    profile = client.get("/users/me", headers=auth(token))
    assert profile.status_code == 200
    assert profile.json()["email"] == user.email
    assert "password_hash" not in profile.json()

    forbidden_role = client.put("/users/me", headers=auth(token), json={"type": "admin"})
    assert forbidden_role.status_code == 422

    updated = client.put(
        "/users/me",
        headers=auth(token),
        json={
            "first_name": "  Leila ",
            "email": "LEILA@example.com",
            "phone": "+961 76 555 444",
            "password": "a newly changed password",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["first_name"] == "Leila"
    assert updated.json()["email"] == "leila@example.com"
    assert updated.json()["phone"] == "+96176555444"
    assert client.get("/users/me", headers=auth(token)).status_code == 401
    assert (
        client.post("/login", json={"email": "leila@example.com", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/login",
            json={"email": "leila@example.com", "password": "a newly changed password"},
        ).status_code
        == 200
    )


def test_profile_rejects_duplicate_email(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    first = create_user(session_factory, email="first@example.com", user_type=SystemUserType.CLIENT)
    create_user(session_factory, email="second@example.com", user_type=SystemUserType.CLIENT)
    token = access_token(client, first.email)

    response = client.put("/users/me", headers=auth(token), json={"email": "SECOND@example.com"})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_admin_create_list_filter_search_paginate_update_and_authorize(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, email="admin@example.com", user_type=SystemUserType.ADMIN)
    client_user = create_user(
        session_factory, email="client@example.com", user_type=SystemUserType.CLIENT
    )
    admin_token = access_token(client, admin.email)
    client_token = access_token(client, client_user.email)

    assert (
        client.post(
            "/users", headers=auth(client_token), json=user_payload("denied@example.com")
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/users/{admin.id}", headers=auth(client_token), json={"city": "Denied"}
        ).status_code
        == 403
    )
    created = client.post(
        "/users",
        headers=auth(admin_token),
        json=user_payload("maya@example.com", type="admin"),
    )
    assert created.status_code == 201, created.text
    assert created.json()["type"] == "admin"

    created_client = client.post(
        "/users",
        headers=auth(admin_token),
        json=user_payload("created.client@example.com", type="client", first_name="Rami"),
    )
    assert created_client.status_code == 201, created_client.text
    assert created_client.json()["type"] == "client"

    client.post(
        "/users",
        headers=auth(admin_token),
        json=user_payload(
            "omar@example.com",
            first_name="Omar",
            last_name="Saleh",
            city="Tripoli",
            age=40,
        ),
    )
    filtered = client.get(
        "/users",
        headers=auth(admin_token),
        params={
            "city": "tripoli",
            "age": 40,
            "type": "client",
            "search": "OMAR",
            "page": 1,
            "limit": 1,
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["users"][0]["email"] == "omar@example.com"

    page = client.get("/users", headers=auth(admin_token), params={"page": 2, "limit": 2})
    assert page.status_code == 200
    assert page.json()["page"] == 2
    assert page.json()["limit"] == 2
    assert page.json()["total"] == 5
    assert page.json()["total_pages"] == 3

    updated = client.put(
        f"/users/{client_user.id}",
        headers=auth(admin_token),
        json={"type": "admin", "city": "Sidon"},
    )
    assert updated.status_code == 200
    assert updated.json()["type"] == "admin"
    assert updated.json()["city"] == "Sidon"
    assert client.get("/users", headers=auth(client_token)).status_code == 401
    assert (
        client.put(
            "/users/00000000-0000-0000-0000-000000000001",
            headers=auth(admin_token),
            json={"city": "Tyre"},
        ).status_code
        == 404
    )


def test_soft_delete_excludes_user_from_login_list_and_statistics(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(
        session_factory, email="admin@example.com", user_type=SystemUserType.ADMIN, age=40
    )
    target = create_user(
        session_factory,
        email="target@example.com",
        user_type=SystemUserType.CLIENT,
        city="Beirut",
        age=20,
    )
    token = access_token(client, admin.email)
    assert client.get("/stats/count").json() == {"count": 2}
    assert client.get("/stats/average-age").json() == {"average_age": 30.0}

    response = client.delete(f"/users/{target.id}", headers=auth(token))

    assert response.status_code == 204
    assert (
        client.post("/login", json={"email": target.email, "password": PASSWORD}).status_code == 401
    )
    listed = client.get("/users", headers=auth(token)).json()
    assert listed["total"] == 1
    assert client.get("/stats/count").json() == {"count": 1}
    assert client.get("/stats/average-age").json() == {"average_age": 40.0}


def test_public_statistics_empty_and_top_cities_have_stable_tie_break(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    assert client.get("/stats/count").json() == {"count": 0}
    assert client.get("/stats/average-age").json() == {"average_age": None}
    assert client.get("/stats/top-cities").json() == []

    create_user(
        session_factory,
        email="a@example.com",
        user_type=SystemUserType.CLIENT,
        city="Tripoli",
    )
    create_user(
        session_factory,
        email="b@example.com",
        user_type=SystemUserType.CLIENT,
        city="beirut",
    )
    create_user(
        session_factory,
        email="c@example.com",
        user_type=SystemUserType.CLIENT,
        city="Beirut",
    )
    create_user(
        session_factory,
        email="d@example.com",
        user_type=SystemUserType.CLIENT,
        city="Sidon",
    )
    create_user(
        session_factory,
        email="e@example.com",
        user_type=SystemUserType.CLIENT,
        city="Byblos",
    )

    assert client.get("/stats/top-cities").json() == [
        {"city": "Beirut", "count": 2},
        {"city": "Byblos", "count": 1},
        {"city": "Sidon", "count": 1},
    ]


def test_last_active_owner_is_protected_without_partial_changes(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, email="admin@example.com", user_type=SystemUserType.ADMIN)
    owner = create_user(session_factory, email="owner@example.com", user_type=SystemUserType.CLIENT)
    with session_factory() as db:
        tenant = Tenant(
            name="Owner Van", status=TenantStatus.ACTIVE, activated_at=datetime.now(UTC)
        )
        db.add(tenant)
        db.flush()
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=owner.id,
            role=TenantRole.OWNER,
            is_active=True,
        )
        db.add(membership)
        db.commit()
        membership_id = membership.id
    token = access_token(client, admin.email)

    response = client.delete(f"/users/{owner.id}", headers=auth(token))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OWNER_TRANSFER_REQUIRED"
    with session_factory() as db:
        stored_user = db.get(User, owner.id)
        stored_membership = db.get(TenantMembership, membership_id)
        assert stored_user is not None and stored_user.is_deleted is False
        assert stored_membership is not None and stored_membership.is_active is True


def test_deleting_one_of_two_owners_revokes_membership_atomically(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    admin = create_user(session_factory, email="admin@example.com", user_type=SystemUserType.ADMIN)
    first_owner = create_user(
        session_factory, email="first.owner@example.com", user_type=SystemUserType.CLIENT
    )
    second_owner = create_user(
        session_factory, email="second.owner@example.com", user_type=SystemUserType.CLIENT
    )
    with session_factory() as db:
        tenant = Tenant(
            name="Shared Van", status=TenantStatus.ACTIVE, activated_at=datetime.now(UTC)
        )
        db.add(tenant)
        db.flush()
        first_membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=first_owner.id,
            role=TenantRole.OWNER,
            is_active=True,
        )
        db.add_all(
            [
                first_membership,
                TenantMembership(
                    tenant_id=tenant.id,
                    user_id=second_owner.id,
                    role=TenantRole.OWNER,
                    is_active=True,
                ),
            ]
        )
        db.commit()
        first_membership_id = first_membership.id
    token = access_token(client, admin.email)

    response = client.delete(f"/users/{first_owner.id}", headers=auth(token))

    assert response.status_code == 204
    with session_factory() as db:
        stored_user = db.get(User, first_owner.id)
        membership = db.get(TenantMembership, first_membership_id)
        assert stored_user is not None and stored_user.is_deleted is True
        assert membership is not None and membership.is_active is False
        assert membership.revoked_at is not None


def test_concurrent_owner_deletions_cannot_orphan_active_tenant(
    session_factory: sessionmaker[Session],
) -> None:
    first_owner = create_user(
        session_factory, email="first.owner@example.com", user_type=SystemUserType.CLIENT
    )
    second_owner = create_user(
        session_factory, email="second.owner@example.com", user_type=SystemUserType.CLIENT
    )
    with session_factory() as db:
        tenant = Tenant(
            name="Concurrent Owners",
            status=TenantStatus.ACTIVE,
            activated_at=datetime.now(UTC),
        )
        db.add(tenant)
        db.flush()
        tenant_id = tenant.id
        db.add_all(
            [
                TenantMembership(
                    tenant_id=tenant.id,
                    user_id=first_owner.id,
                    role=TenantRole.OWNER,
                    is_active=True,
                ),
                TenantMembership(
                    tenant_id=tenant.id,
                    user_id=second_owner.id,
                    role=TenantRole.OWNER,
                    is_active=True,
                ),
            ]
        )
        db.commit()

    def delete(user_id: object) -> str:
        with session_factory() as db:
            try:
                soft_delete_user(db, user_id)  # type: ignore[arg-type]
            except AppError as exc:
                return exc.code
        return "DELETED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(delete, [first_owner.id, second_owner.id]))

    assert sorted(results) == ["DELETED", "OWNER_TRANSFER_REQUIRED"]
    with session_factory() as db:
        usable_owners = list(
            db.scalars(
                select(TenantMembership)
                .join(User, User.id == TenantMembership.user_id)
                .where(
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.role == TenantRole.OWNER,
                    TenantMembership.is_active.is_(True),
                    User.is_deleted.is_(False),
                )
            )
        )
        assert len(usable_owners) == 1
