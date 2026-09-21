"""Client-IP resolution for the abuse controls (audit finding TWZ-F-005).

Direct exposure ignores forwarded headers; behind `TRUSTED_PROXY_HOPS` proxies the client is the
n-th address from the right of X-Forwarded-For, so a caller cannot pick its own throttle key and
visitors behind one proxy do not share one bucket."""

from __future__ import annotations

import pytest
from test_auth import register

from tawzeevo_api.client_ip import header_value, resolve_client_ip
from tawzeevo_api.routes import auth as auth_routes


@pytest.mark.parametrize(
    ("peer", "forwarded", "hops", "expected"),
    [
        ("10.0.0.7", None, 0, "10.0.0.7"),
        ("10.0.0.7", "203.0.113.9", 0, "10.0.0.7"),  # direct: header ignored
        ("10.0.0.7", "203.0.113.9", 1, "203.0.113.9"),
        ("10.0.0.7", "198.51.100.1, 203.0.113.9", 1, "203.0.113.9"),  # spoofed prefix ignored
        ("10.0.0.7", "198.51.100.1, 203.0.113.9, 10.0.0.8", 2, "203.0.113.9"),
        ("10.0.0.7", "203.0.113.9", 2, "10.0.0.7"),  # fewer hops than trusted: peer wins
        ("10.0.0.7", "", 1, "10.0.0.7"),
        (None, None, 0, "unknown"),
        (None, "203.0.113.9", 1, "203.0.113.9"),
    ],
)
def test_resolution_rule(peer, forwarded, hops, expected):
    assert resolve_client_ip(peer, forwarded, hops) == expected


def test_header_value_reads_the_raw_asgi_headers():
    headers = [(b"host", b"x"), (b"X-Forwarded-For", b"203.0.113.9, 10.0.0.1")]
    assert header_value(headers, b"x-forwarded-for") == "203.0.113.9, 10.0.0.1"
    assert header_value(headers, b"x-real-ip") is None


@pytest.fixture(autouse=True)
def _fresh_limiters():
    auth_routes.reset_auth_limiters()
    yield
    auth_routes.reset_auth_limiters()


def _configured(monkeypatch, hops: int):
    from tawzeevo_api.config import get_settings

    configured = get_settings().model_copy(update={"trusted_proxy_hops": hops})
    monkeypatch.setattr(auth_routes, "get_settings", lambda: configured)


def test_direct_deployment_ignores_forwarded_headers_for_login_throttling(client, monkeypatch):
    _configured(monkeypatch, 0)
    register(client)
    bad = {"email": "layla.haddad@example.com", "password": "wrong password here"}
    # Ten failures with ten different forged X-Forwarded-For values still share the peer bucket.
    codes = [
        client.post("/login", json=bad, headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
        for i in range(11)
    ]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_behind_one_trusted_proxy_the_forwarded_client_is_the_throttle_key(client, monkeypatch):
    _configured(monkeypatch, 1)
    register(client)
    bad = {"email": "layla.haddad@example.com", "password": "wrong password here"}
    attacker = {"X-Forwarded-For": "203.0.113.9"}
    codes = [client.post("/login", json=bad, headers=attacker).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    # A different visitor behind the same proxy is not blocked by the attacker's failures ...
    other = client.post("/login", json=bad, headers={"X-Forwarded-For": "198.51.100.4"})
    assert other.status_code == 401
    # ... and the attacker cannot escape the window by prepending addresses to the header:
    # the proxy appends the real peer last, and the last hop is what is keyed.
    spoofed = client.post(
        "/login", json=bad, headers={"X-Forwarded-For": "198.51.100.77, 203.0.113.9"}
    )
    assert spoofed.status_code == 429
