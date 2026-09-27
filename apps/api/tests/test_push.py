"""D-116: web push subscriptions, fan-out after commit, cleanup of gone subscriptions."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
from sqlalchemy import select, text
from test_delivery_tasks import _driver, _post
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _login, _owner_context, _user
from test_procurement import _confirm_invoice

from tawzeevo_api.config import get_settings
from tawzeevo_api.models import PushSubscription, SystemUserType
from tawzeevo_api.services import push


def _sub(n: int) -> dict[str, object]:
    return {
        "endpoint": f"https://push.example.test/send/{n}",
        "keys": {"p256dh": f"k{n}", "auth": f"a{n}"},
    }


class Sent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.fail: dict[str, int] = {}

    def __call__(self, info: dict[str, object], payload: str) -> None:
        endpoint = str(info["endpoint"])
        if endpoint in self.fail:
            error = RuntimeError("push service refused")
            error.response = type("R", (), {"status_code": self.fail[endpoint]})()  # type: ignore[attr-defined]
            raise error
        self.calls.append((endpoint, json.loads(payload)))


@pytest.fixture
def push_on(monkeypatch, session_factory):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "BPublicKeyForTests")
    monkeypatch.setattr(settings, "vapid_private_key", "private-key-for-tests")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:owner@example.com")
    monkeypatch.setattr(push, "SESSION_FACTORY", session_factory)
    sent = Sent()
    monkeypatch.setattr(push, "_send", sent)
    return sent


def _rows(session_factory, user_id=None):
    with session_factory() as db:
        db.execute(text("SELECT set_config('app.push_delivery', 'true', true)"))
        query = select(PushSubscription)
        if user_id is not None:
            query = query.where(PushSubscription.user_id == user_id)
        return list(db.scalars(query))


def test_public_key_and_own_subscriptions(client, session_factory, monkeypatch):
    viewer = _user(session_factory, "push-viewer@example.com", SystemUserType.CLIENT)
    viewer_auth = _auth(_login(client, viewer.email))
    assert client.get("/api/v1/push/public-key").status_code == 401
    assert client.get("/api/v1/push/public-key", headers=viewer_auth).json() == {
        "enabled": False,
        "public_key": None,
    }
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", "BPublicKeyForTests")
    monkeypatch.setattr(settings, "vapid_private_key", "private")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:owner@example.com")
    assert client.get("/api/v1/push/public-key", headers=viewer_auth).json() == {
        "enabled": True,
        "public_key": "BPublicKeyForTests",
    }

    alice = _user(session_factory, "push-alice@example.com", SystemUserType.CLIENT)
    bob = _user(session_factory, "push-bob@example.com", SystemUserType.CLIENT)
    alice_token, bob_token = _login(client, alice.email), _login(client, bob.email)
    assert client.post("/api/v1/push/subscriptions", json=_sub(1)).status_code == 401
    for _ in range(2):  # the same endpoint again updates it (upsert)
        created = client.post(
            "/api/v1/push/subscriptions", headers=_auth(alice_token), json=_sub(1)
        )
        assert created.status_code == 204, created.text
    changed = {**_sub(1), "keys": {"p256dh": "new", "auth": "new"}}
    client.post("/api/v1/push/subscriptions", headers=_auth(alice_token), json=changed)
    rows = _rows(session_factory, alice.id)
    assert len(rows) == 1 and rows[0].p256dh == "new"
    state = client.post(
        "/api/v1/push/subscriptions/state",
        headers=_auth(alice_token),
        json={"endpoint": _sub(1)["endpoint"]},
    )
    assert state.json() == {"subscribed": True}
    # Another person cannot remove (or see) Alice's subscription.
    other = client.request(
        "DELETE",
        "/api/v1/push/subscriptions",
        headers=_auth(bob_token),
        json={"endpoint": _sub(1)["endpoint"]},
    )
    assert other.status_code == 204
    assert len(_rows(session_factory, alice.id)) == 1
    assert client.post(
        "/api/v1/push/subscriptions/state",
        headers=_auth(bob_token),
        json={"endpoint": _sub(1)["endpoint"]},
    ).json() == {"subscribed": False}
    removed = client.request(
        "DELETE",
        "/api/v1/push/subscriptions",
        headers=_auth(alice_token),
        json={"endpoint": _sub(1)["endpoint"]},
    )
    assert removed.status_code == 204
    assert _rows(session_factory, alice.id) == []
    assert (
        client.post(
            "/api/v1/push/subscriptions",
            headers=_auth(alice_token),
            json={**_sub(2), "endpoint": "http://insecure"},
        ).status_code
        == 422
    )


def test_new_order_reaches_only_that_business_owners(client, session_factory, push_on):
    from test_order_review import _place
    from test_storefront import _publish

    owner_a, tenant_a, token_a = _owner_context(client, session_factory, "pusha")
    _owner_b, _tenant_b, token_b = _owner_context(client, session_factory, "pushb")
    client.post("/api/v1/push/subscriptions", headers=_auth(token_a), json=_sub(10))
    client.post("/api/v1/push/subscriptions", headers=_auth(token_b), json=_sub(20))
    _category, product, _customer = _catalog(client, tenant_a, token_a, name="Cedar Water")
    _publish(client, tenant_a, token_a, product["id"])
    _place(client, session_factory, owner_a, tenant_a, token_a, product)
    assert [endpoint for endpoint, _payload in push_on.calls] == [_sub(10)["endpoint"]]
    payload = push_on.calls[0][1]
    assert set(payload) == {"title", "body", "url"}
    assert payload["url"] == f"/workspace?section=orders&tenant={tenant_a}"
    assert not any(ch.isdigit() for ch in payload["body"])  # no amounts in the message


def test_assignment_reaches_only_the_driver_and_gone_subscriptions_are_removed(
    client, session_factory, push_on
):
    owner, tenant, token = _owner_context(client, session_factory, "pushdrv")
    _category, product, customer = _catalog(client, tenant, token, name="Bread")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    invoice = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    driver, driver_token, driver_membership = _driver(
        client, session_factory, tenant, "push-driver@example.com"
    )
    _other, other_token, _other_membership = _driver(
        client, session_factory, tenant, "push-other@example.com"
    )
    client.post("/api/v1/push/subscriptions", headers=_auth(token), json=_sub(30))
    client.post("/api/v1/push/subscriptions", headers=_auth(driver_token), json=_sub(31))
    client.post("/api/v1/push/subscriptions", headers=_auth(driver_token), json=_sub(32))
    client.post("/api/v1/push/subscriptions", headers=_auth(other_token), json=_sub(33))
    push_on.fail = {str(_sub(32)["endpoint"]): 410}
    created = _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {"invoice_id": invoice["id"], "assigned_membership_id": driver_membership},
    )
    assert created.status_code == 201, created.text
    assert [endpoint for endpoint, _p in push_on.calls] == [_sub(31)["endpoint"]]
    assert push_on.calls[0][1]["url"] == f"/workspace?tenant={tenant}"
    endpoints = {row.endpoint for row in _rows(session_factory, driver.id)}
    assert endpoints == {_sub(31)["endpoint"]}  # the 410 one was deleted

    # Another failure is counted, not deleted.
    push_on.calls.clear()
    push_on.fail = {str(_sub(31)["endpoint"]): 500}
    reassigned = client.put(
        f"/api/v1/delivery-tasks/{created.json()['id']}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={
            "assigned_membership_id": _other_membership,
            "expected_version": created.json()["version"],
        },
    )
    assert reassigned.status_code == 200, reassigned.text
    assert [endpoint for endpoint, _p in push_on.calls] == [_sub(33)["endpoint"]]


def test_nothing_is_sent_without_keys(client, session_factory, monkeypatch):
    sent = Sent()
    monkeypatch.setattr(push, "_send", sent)
    monkeypatch.setattr(push, "SESSION_FACTORY", session_factory)
    owner = _user(session_factory, "push-off@example.com", SystemUserType.CLIENT)
    token = _login(client, owner.email)
    client.post("/api/v1/push/subscriptions", headers=_auth(token), json=_sub(40))
    assert push.notify_users([owner.id], "t", "b", "/") == 0
    assert sent.calls == []
    assert isinstance(owner.id, UUID)


def test_row_level_security_shows_only_own_subscriptions(client, session_factory, test_engine):
    """Under a non-bypass role, a user sees only their own rows; the sender scope sees all."""

    alice = _user(session_factory, "push-rls-a@example.com", SystemUserType.CLIENT)
    bob = _user(session_factory, "push-rls-b@example.com", SystemUserType.CLIENT)
    client.post(
        "/api/v1/push/subscriptions", headers=_auth(_login(client, alice.email)), json=_sub(50)
    )
    client.post(
        "/api/v1/push/subscriptions", headers=_auth(_login(client, bob.email)), json=_sub(51)
    )
    role = "tawzeevo_push_rls_check"
    with test_engine.connect() as connection:
        connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
        connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
        connection.exec_driver_sql(f'GRANT SELECT ON push_subscriptions TO "{role}"')
        connection.commit()
        try:
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{role}"')
                connection.execute(
                    text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(bob.id)}
                )
                seen = connection.execute(text("SELECT endpoint FROM push_subscriptions")).scalars()
                assert list(seen) == [_sub(51)["endpoint"]]
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{role}"')
                assert (
                    connection.execute(text("SELECT count(*) FROM push_subscriptions")).scalar_one()
                    == 0
                )
        finally:
            connection.exec_driver_sql(f'REVOKE ALL ON push_subscriptions FROM "{role}"')
            connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
            connection.commit()
