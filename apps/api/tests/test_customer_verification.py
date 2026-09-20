"""Phase 9 P9-M5 (PHASE_09.md, D-072/D-073): customer verification challenges, verified
sessions, abuse controls, provider outage, isolation, and the LINK vs VERIFIED policies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_checkout import _cart, _checkout
from test_customer_access import HEADER, _catalog_prices, _issue
from test_invoice_editor import _auth, _catalog, _login, _owner_context
from test_storefront import _publish, _slug

from tawzeevo_api import metrics
from tawzeevo_api.models import (
    AuditEvent,
    CustomerVerificationChallenge,
    CustomerVerifiedSession,
    Order,
)
from tawzeevo_api.services.otp_delivery import dev_delivery

SESSION = "X-Customer-Session"
START = "/api/v1/public/customer-verification/start"
CONFIRM = "/api/v1/public/customer-verification/confirm"
DEV_CODE = "/api/v1/public/customer-verification/dev-code"


@pytest.fixture(autouse=True)
def _clean_metrics():
    metrics.reset_for_tests()
    dev_delivery().fail_next = False


def _verified_business(client, session_factory, suffix):
    owner, tenant, token = _owner_context(client, session_factory, suffix)
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    assert client.put(
        f"/api/v1/tenants/{tenant}/grade-discounts/A",
        headers=_auth(token),
        json={"discount_percent": "20.00"},
    ).status_code in (200, 201)
    policy = client.put(
        f"/api/v1/tenants/{tenant}/storefront/access-policy",
        headers=_auth(token),
        json={"policy": "VERIFIED"},
    )
    assert policy.status_code == 200, policy.text
    return owner, tenant, token, product, customer, slug


def _code(client, secret):
    response = client.get(DEV_CODE, headers={HEADER: secret})
    assert response.status_code == 200, response.text
    return response.json()["code"]


def test_link_alone_is_not_enough_under_verified_and_the_code_grants_a_session(
    client, session_factory
):
    _owner, tenant, token, product, customer, slug = _verified_business(
        client, session_factory, "v1"
    )
    _issued, secret = _issue(client, tenant, token, customer["id"])

    # The link resolves (the storefront can offer verification) but grants nothing yet.
    state = client.get("/api/v1/public/customer-context", headers={HEADER: secret}).json()
    assert state["assurance"] == "LINK" and state["required_policy"] == "VERIFIED"
    assert state["granted"] is False and state["contact_hint"].startswith("…")
    assert len(state["contact_hint"]) == 4  # masked: last three digits only
    _response, prices = _catalog_prices(client, slug, secret)
    assert prices["Cedar Water"] == (product["unit_price"], "public")  # anonymous pricing
    order = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret})
    assert order.status_code == 201
    with session_factory() as db:
        row = db.scalars(select(Order)).one()
        assert row.intended_customer_id is None and row.intended_assurance is None

    # Start → the dev adapter holds the code; the code is stored hashed, never in audit.
    started = client.post(START, headers={HEADER: secret, "Accept-Language": "ar"})
    assert started.status_code == 202, started.text
    code = _code(client, secret)
    assert len(code) == 6 and code.isdigit()
    with session_factory() as db:
        challenge = db.scalars(select(CustomerVerificationChallenge)).one()
        assert challenge.code_sha256 != code and challenge.channel == "dev"
        assert (
            timedelta(minutes=4) < challenge.expires_at - datetime.now(UTC) <= timedelta(minutes=5)
        )
        audits = db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("customer_verif%"))
        ).all()
        assert code not in str([a.details for a in audits])

    # Wrong code, then the right one: a session appears and the same link now grants pricing.
    wrong = client.post(CONFIRM, json={"code": "000000"}, headers={HEADER: secret})
    assert (
        wrong.status_code == 400 and wrong.json()["detail"]["code"] == "VERIFICATION_CODE_INVALID"
    )
    confirmed = client.post(CONFIRM, json={"code": code}, headers={HEADER: secret})
    assert confirmed.status_code == 200, confirmed.text
    session_secret = confirmed.json()["session"]
    assert session_secret.startswith(tenant.replace("-", "")) and "." in session_secret
    reused = client.post(CONFIRM, json={"code": code}, headers={HEADER: secret})
    assert reused.status_code == 400  # single use
    state = client.get(
        "/api/v1/public/customer-context", headers={HEADER: secret, SESSION: session_secret}
    ).json()
    assert state["assurance"] == "VERIFIED" and state["granted"] is True
    assert state["contact_hint"] == ""
    _response, prices = _catalog_prices(client, slug, secret)
    assert prices["Cedar Water"] == (product["unit_price"], "public")  # link alone: still public
    personalized = client.get(
        f"/api/v1/public/{slug}/catalog/products", headers={HEADER: secret, SESSION: session_secret}
    )
    assert personalized.status_code == 200
    assert {r["name"]: r["price"] for r in personalized.json()["items"]}["Cedar Water"] == "10.0000"
    assert personalized.headers["vary"] == f"{HEADER}, {SESSION}"
    order = _checkout(
        client, slug, _cart(product["id"]), extra={HEADER: secret, SESSION: session_secret}
    )
    assert order.status_code == 201
    with session_factory() as db:
        rows = db.scalars(select(Order).order_by(Order.created_at)).all()
        assert rows[-1].intended_assurance == "VERIFIED"
        assert str(rows[-1].intended_customer_id) == customer["id"]

    # A session stolen for another customer's link is worthless; a wrong-tenant one too.
    _o2, tenant2, token2, _p2, customer2, _s2 = _verified_business(client, session_factory, "v2")
    _i2, secret2 = _issue(client, tenant2, token2, customer2["id"])
    cross = client.get(
        "/api/v1/public/customer-context", headers={HEADER: secret2, SESSION: session_secret}
    ).json()
    assert cross["assurance"] == "LINK" and cross["granted"] is False

    # Customer-initiated sign-out; the link keeps working for a new verification.
    assert (
        client.delete(
            "/api/v1/public/customer-verification/session",
            headers={HEADER: secret, SESSION: session_secret},
        ).status_code
        == 204
    )
    state = client.get(
        "/api/v1/public/customer-context", headers={HEADER: secret, SESSION: session_secret}
    ).json()
    assert state["granted"] is False
    body = client.get("/health/metrics").json()
    assert body["otp_sent"] == 1 and body["otp_verified"] == 1 and body["otp_wrong"] == 1


def test_expiry_lockout_throttle_outage_and_revocations(client, session_factory, monkeypatch):
    _owner, tenant, token, product, customer, slug = _verified_business(
        client, session_factory, "v3"
    )
    _issued, secret = _issue(client, tenant, token, customer["id"])

    # Expired challenge is refused and closed.
    assert client.post(START, headers={HEADER: secret}).status_code == 202
    code = _code(client, secret)
    with session_factory() as db:
        challenge = db.scalars(select(CustomerVerificationChallenge)).one()
        challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.post(CONFIRM, json={"code": code}, headers={HEADER: secret}).status_code == 400

    # Lockout: five wrong attempts consume the challenge; the right code no longer works.
    assert client.post(START, headers={HEADER: secret}).status_code == 202
    code = _code(client, secret)
    for _ in range(5):
        assert (
            client.post(CONFIRM, json={"code": "111111"}, headers={HEADER: secret}).status_code
            == 400
        )
    assert client.post(CONFIRM, json={"code": code}, headers={HEADER: secret}).status_code == 400
    assert client.get("/health/metrics").json()["otp_locked"] == 1

    # Throttle: at most five starts per hour per customer.
    for _ in range(3):
        assert client.post(START, headers={HEADER: secret}).status_code == 202
    throttled = client.post(START, headers={HEADER: secret})
    assert throttled.status_code == 429
    assert throttled.json()["detail"]["code"] == "VERIFICATION_RATE_LIMITED"

    # Provider outage: clean 503, nothing usable left behind, the customer is not locked in.
    with session_factory() as db:
        for row in db.scalars(select(CustomerVerificationChallenge)):
            row.created_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
    dev_delivery().fail_next = True
    outage = client.post(START, headers={HEADER: secret})
    assert outage.status_code == 503
    assert outage.json()["detail"]["code"] == "VERIFICATION_UNAVAILABLE"
    with session_factory() as db:
        latest = db.scalars(
            select(CustomerVerificationChallenge).order_by(
                CustomerVerificationChallenge.created_at.desc()
            )
        ).first()
        assert latest is not None and latest.consumed_reason == "delivery_failed"
    assert client.post(START, headers={HEADER: secret}).status_code == 202  # recovered

    # A verified session ends with the link (rotation) and with an owner revocation.
    code = _code(client, secret)
    session_secret = client.post(CONFIRM, json={"code": code}, headers={HEADER: secret}).json()[
        "session"
    ]
    status = client.get(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(token)
    ).json()
    assert status["verified_sessions"] == 1 and "VERIFIED" in status["available_policies"]
    revoked = client.post(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}/verified-sessions/revoke",
        headers=_auth(token),
    )
    assert revoked.status_code == 200 and revoked.json()["verified_sessions"] == 0
    state = client.get(
        "/api/v1/public/customer-context", headers={HEADER: secret, SESSION: session_secret}
    ).json()
    assert state["granted"] is False
    with session_factory() as db:
        for row in db.scalars(select(CustomerVerificationChallenge)):
            row.created_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
    assert client.post(START, headers={HEADER: secret}).status_code == 202
    code = _code(client, secret)
    session_secret = client.post(CONFIRM, json={"code": code}, headers={HEADER: secret}).json()[
        "session"
    ]
    _rotated, new_secret = _issue(client, tenant, token, customer["id"])  # rotation
    with session_factory() as db:
        sessions = db.scalars(select(CustomerVerifiedSession)).all()
        assert all(s.revoked_at is not None for s in sessions)
        assert {s.revoked_reason for s in sessions} == {"owner_revoked", "link_rotated"}
    assert (
        client.get("/api/v1/public/customer-context", headers={HEADER: secret}).status_code == 404
    )
    state = client.get(
        "/api/v1/public/customer-context", headers={HEADER: new_secret, SESSION: session_secret}
    ).json()
    assert state["granted"] is False

    # Expired session is not honoured; a phone change never breaks identity.
    with session_factory() as db:
        for row in db.scalars(select(CustomerVerificationChallenge)):
            row.created_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
    assert client.post(START, headers={HEADER: new_secret}).status_code == 202
    code = _code(client, new_secret)
    session_secret = client.post(CONFIRM, json={"code": code}, headers={HEADER: new_secret}).json()[
        "session"
    ]
    assert (
        client.put(
            f"/api/v1/tenants/{tenant}/customers/{customer['id']}",
            headers=_auth(token),
            json={"phone": "+96171999888"},
        ).status_code
        == 200
    )
    state = client.get(
        "/api/v1/public/customer-context", headers={HEADER: new_secret, SESSION: session_secret}
    ).json()
    assert state["granted"] is True and state["display_name"] == customer["name"]
    with session_factory() as db:
        session = db.scalars(
            select(CustomerVerifiedSession).where(CustomerVerifiedSession.revoked_at.is_(None))
        ).one()
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    state = client.get(
        "/api/v1/public/customer-context", headers={HEADER: new_secret, SESSION: session_secret}
    ).json()
    assert state["granted"] is False

    # Suspension: the link (and any session) is unavailable at once.
    admin_token = _login(client, "admin-v3@example.com")
    assert (
        client.post(
            f"/api/v1/platform/tenants/{tenant}/suspend", headers=_auth(admin_token)
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/public/customer-context", headers={HEADER: new_secret}).status_code
        == 404
    )
    assert client.post(START, headers={HEADER: new_secret}).status_code == 404


def test_link_policy_customers_are_unaffected_and_dev_code_is_guarded(
    client, session_factory, monkeypatch
):
    _owner, tenant, token = _owner_context(client, session_factory, "v4")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    _issued, secret = _issue(client, tenant, token, customer["id"])
    state = client.get("/api/v1/public/customer-context", headers={HEADER: secret}).json()
    assert state == {
        "assurance": "LINK",
        "tenant_slug": _slug(session_factory, tenant),
        "display_name": customer["name"],
        "required_policy": "LINK",
        "granted": True,
        "contact_hint": "",
    }
    # ACCOUNT_REQUIRED is still not selectable (P9-M6).
    refused = client.put(
        f"/api/v1/tenants/{tenant}/storefront/access-policy",
        headers=_auth(token),
        json={"policy": "ACCOUNT_REQUIRED"},
    )
    assert refused.status_code == 409
    # The dev code endpoint disappears outside the development adapter.
    from tawzeevo_api.config import get_settings

    monkeypatch.setattr(get_settings(), "customer_otp_provider", "whatsapp")
    assert client.get(DEV_CODE, headers={HEADER: secret}).status_code == 404
    # ... and an unconfigured production channel fails safely (503, no code stored as usable).
    client.put(
        f"/api/v1/tenants/{tenant}/storefront/access-policy",
        headers=_auth(token),
        json={"policy": "VERIFIED"},
    )
    outage = client.post(START, headers={HEADER: secret})
    assert outage.status_code == 503
