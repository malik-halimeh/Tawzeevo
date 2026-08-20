from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tawzeevo_api.config import Settings, get_settings
from tawzeevo_api.main import app
from tawzeevo_api.models import AuthSession, SystemUserType, User
from tawzeevo_api.security import create_access_token, hash_refresh_token


def registration_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "  Layla  ",
        "last_name": "  Haddad  ",
        "email": "  LAYLA.HADDAD@example.com  ",
        "phone": "+961 70 123 456",
        "city": "  Beirut  ",
        "age": 31,
        "password": "correct horse battery staple",
    }
    payload.update(overrides)
    return payload


def register(client: TestClient, **overrides: object) -> dict[str, object]:
    response = client.post("/register", json=registration_payload(**overrides))
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def login(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": "layla.haddad@example.com",
        "password": "correct horse battery staple",
    }
    payload.update(overrides)
    response = client.post("/login", json=payload)
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


def test_registration_normalizes_and_returns_safe_client(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    body = register(client)

    assert body["first_name"] == "Layla"
    assert body["last_name"] == "Haddad"
    assert body["email"] == "layla.haddad@example.com"
    assert body["phone"] == "+96170123456"
    assert body["city"] == "Beirut"
    assert body["type"] == "client"
    assert "password" not in body
    assert "password_hash" not in body

    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == "layla.haddad@example.com"))
        assert user is not None
        assert user.type is SystemUserType.CLIENT
        assert user.phone_raw == "+961 70 123 456"
        assert user.password_hash.startswith("$argon2id$")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("phone", "123"),
        ("age", 0),
        ("age", 121),
        ("first_name", "   "),
        ("last_name", "\t"),
        ("city", "  "),
        ("password", "short"),
        ("password", " " * 10),
        ("password", "x" * 129),
    ],
)
def test_registration_validation(client: TestClient, field: str, value: object) -> None:
    response = client.post("/register", json=registration_payload(**{field: value}))

    assert response.status_code == 422


def test_registration_rejects_privileged_type(client: TestClient) -> None:
    response = client.post("/register", json=registration_payload(type="admin"))

    assert response.status_code == 422


def test_registration_rejects_duplicate_normalized_email(client: TestClient) -> None:
    register(client)

    response = client.post("/register", json=registration_payload(email="LAYLA.HADDAD@EXAMPLE.COM"))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_login_creates_session_access_token_and_scoped_cookie(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    register(client)

    response = client.post(
        "/login",
        json={
            "email": "  LAYLA.HADDAD@example.com ",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 900
    assert response.json()["access_token"]
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/api/v1/auth" in set_cookie

    settings = get_settings()
    raw_refresh_token = response.cookies[settings.refresh_cookie_name]
    claims = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == 15 * 60

    with session_factory() as db:
        auth_session = db.scalar(select(AuthSession))
        assert auth_session is not None
        assert auth_session.refresh_token_hash == hash_refresh_token(raw_refresh_token)
        assert raw_refresh_token not in auth_session.refresh_token_hash
        remaining = auth_session.expires_at - datetime.now(UTC)
        assert timedelta(days=29, hours=23) < remaining <= timedelta(days=30)


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("layla.haddad@example.com", "wrong-password"),
        ("missing@example.com", "correct horse battery staple"),
    ],
)
def test_login_rejects_incorrect_credentials(client: TestClient, email: str, password: str) -> None:
    register(client)

    response = client.post("/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_soft_deleted_user(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    register(client)
    with session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        user.is_deleted = True
        user.deleted_at = datetime.now(UTC)
        db.commit()

    response = client.post(
        "/login",
        json={
            "email": "layla.haddad@example.com",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize("authorization", [None, "Bearer not-a-jwt", "Basic credentials"])
def test_logout_rejects_missing_or_invalid_access_token(
    client: TestClient, authorization: str | None
) -> None:
    headers = {"Authorization": authorization} if authorization else {}

    response = client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 401


def test_expired_access_token_is_rejected(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    register(client)
    login(client)
    with session_factory() as db:
        user = db.scalar(select(User))
        auth_session = db.scalar(select(AuthSession))
        assert user is not None
        assert auth_session is not None
        expired_token = create_access_token(
            user, auth_session, now=datetime.now(UTC) - timedelta(minutes=16)
        )

    response = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


def test_logout_revokes_session_and_clears_cookie(client: TestClient) -> None:
    register(client)
    token = str(login(client)["access_token"])

    response = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    second_response = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert second_response.status_code == 401


def test_refresh_rotates_and_reuse_revokes_all_user_sessions(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    register(client)
    first_access = str(login(client)["access_token"])
    settings = get_settings()
    old_refresh = client.cookies.get(settings.refresh_cookie_name)
    assert old_refresh is not None

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    replacement_access = refresh_response.json()["access_token"]
    replacement_refresh = client.cookies.get(settings.refresh_cookie_name)
    assert replacement_refresh is not None
    assert replacement_refresh != old_refresh
    assert replacement_access != first_access

    with TestClient(app, base_url="https://testserver") as replay_client:
        replay_response = replay_client.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": f"{settings.refresh_cookie_name}={old_refresh}"},
        )
    assert replay_response.status_code == 401
    assert replay_response.json()["detail"]["code"] == "REFRESH_TOKEN_REUSED"
    assert "max-age=0" in replay_response.headers["set-cookie"].lower()

    revoked_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {replacement_access}"},
    )
    assert revoked_response.status_code == 401
    with session_factory() as db:
        active_sessions = db.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.revoked_at.is_(None))
        )
        assert active_sessions == 0


def test_soft_deleted_user_and_security_version_are_checked_on_protected_request(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    register(client)
    token = str(login(client)["access_token"])
    with session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        user.security_version += 1
        db.commit()

    response = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_refresh_requires_cookie(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_openapi_exposes_bearer_authentication(client: TestClient) -> None:
    document = client.get("/openapi.json").json()

    bearer = document["components"]["securitySchemes"]["BearerAuth"]
    assert bearer == {"type": "http", "scheme": "bearer"}
    assert document["paths"]["/api/v1/auth/logout"]["post"]["security"] == [{"BearerAuth": []}]


def test_production_settings_require_secure_cookie_and_real_secret() -> None:
    production = Settings(
        app_env="production",
        jwt_secret="a-production-secret-placeholder-value",
        refresh_cookie_secure=True,
    )
    assert production.refresh_cookie_secure is True

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret="a-production-secret-placeholder-value",
            refresh_cookie_secure=False,
        )
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="change-me", refresh_cookie_secure=True)
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="too-short", refresh_cookie_secure=True)
