"""Phase 5 freeze checks (PHASE_05.md P5-M6): abuse limits are real and configurable (D-076),
private capability paths stay safe across the token lifecycle, and public surfaces leak nothing
private. Only existing behaviour is asserted."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from sqlalchemy import select
from test_checkout import _cart, _checkout
from test_customer_access import HEADER, _catalog_prices, _issue
from test_invoice_editor import _auth, _catalog, _owner_context
from test_storefront import _publish, _slug

from tawzeevo_api.config import get_settings
from tawzeevo_api.main import app
from tawzeevo_api.models import CustomerAccessLink, Order
from tawzeevo_api.public_invoice_security import PublicInvoicePrivacyMiddleware

PRIVATE_WORDS = re.compile(r"grade|debt|balance|cost_price|unit_cost|supplier|driver|ledger", re.I)


@pytest.fixture(autouse=True)
def _fresh_windows(client):
    """The test client shares one address; each test starts with empty rate-limit windows."""
    mw = _middleware()
    mw.limiter._clients.clear()
    mw.catalog_limiter._clients.clear()
    yield
    mw.limiter._clients.clear()
    mw.catalog_limiter._clients.clear()


def _middleware() -> PublicInvoicePrivacyMiddleware:
    stack = app.middleware_stack
    while stack is not None and not isinstance(stack, PublicInvoicePrivacyMiddleware):
        stack = getattr(stack, "app", None)
    assert isinstance(stack, PublicInvoicePrivacyMiddleware)
    return stack


def test_rate_limits_follow_settings_and_are_separate_per_surface(client, session_factory):
    """The private budget (60/min) and the catalog budget (600/min) are read from settings and
    counted separately, so hammering a private path never blocks the shareable catalog."""
    settings = get_settings()
    mw = _middleware()
    assert mw.limiter.limit == settings.public_private_rate_limit_per_minute == 60
    assert mw.catalog_limiter.limit == settings.public_catalog_rate_limit_per_minute == 600

    _owner, tenant, token = _owner_context(client, session_factory, "p5freeze-rl")
    _category, product, _customer = _catalog(client, tenant, token, name="Freeze Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    bogus = {HEADER: "0" * 32 + "." + "A" * 43}
    statuses = [
        client.get("/api/v1/public/customer-context", headers=bogus).status_code
        for _ in range(mw.limiter.limit + 1)
    ]
    assert statuses[: mw.limiter.limit] == [404] * mw.limiter.limit  # constant failure shape
    assert statuses[-1] == 429
    limited = client.get("/api/v1/public/order", headers={"X-Order-Reference": bogus[HEADER]})
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
    assert "no-store" in limited.headers["cache-control"]  # even refusals are private
    catalog = client.get(f"/api/v1/public/{slug}/catalog/products")
    assert catalog.status_code == 200  # a separate budget


def test_link_lifecycle_is_safe_on_every_private_surface(client, session_factory):
    """Rotated and revoked links fail with the same constant 404 on the context endpoint, fall
    back to anonymous pricing on the catalog, and a checkout with a dead link carries no hint."""
    _owner, tenant, token = _owner_context(client, session_factory, "p5freeze-life")
    _category, product, customer = _catalog(client, tenant, token, name="Lifecycle Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    _first, secret_a = _issue(client, tenant, token, customer["id"])
    _second, secret_b = _issue(client, tenant, token, customer["id"])  # rotates A away
    dead = client.get("/api/v1/public/customer-context", headers={HEADER: secret_a})
    live = client.get("/api/v1/public/customer-context", headers={HEADER: secret_b})
    assert dead.status_code == 404 and live.status_code == 200
    assert dead.json() == client.get("/api/v1/public/customer-context").json()
    assert not PRIVATE_WORDS.search(live.text), live.text

    revoked = client.delete(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(token)
    )
    assert revoked.status_code == 200
    after = client.get("/api/v1/public/customer-context", headers={HEADER: secret_b})
    assert after.status_code == 404
    anonymous, public_prices = _catalog_prices(client, slug)
    _with_dead, dead_prices = _catalog_prices(client, slug, secret_b)
    assert dead_prices == public_prices
    assert anonymous.headers["cache-control"] != "private, no-store"

    placed = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret_b})
    assert placed.status_code == 201, placed.text
    with session_factory() as db:
        order = db.scalar(select(Order).where(Order.tenant_id == UUID(tenant)))
        assert order is not None
        assert order.intended_customer_id is None and order.intended_assurance is None
        links = db.scalars(
            select(CustomerAccessLink).where(CustomerAccessLink.tenant_id == UUID(tenant))
        ).all()
        assert len(links) == 2 and all(link.revoked_at is not None for link in links)
        assert all(len(link.token_sha256) == 64 for link in links)  # hash-only storage
        for link in links:
            assert secret_a not in link.token_sha256 and secret_b not in link.token_sha256


def test_public_surfaces_carry_no_private_data_and_correct_cache_policy(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "p5freeze-leak")
    _category, product, customer = _catalog(client, tenant, token, name="Leak Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    _link, secret = _issue(client, tenant, token, customer["id"])
    placed = _checkout(client, slug, _cart(product["id"]), extra={HEADER: secret})
    reference = placed.json()["provisional_path"].split("#", 1)[1]

    for path in (
        f"/api/v1/public/{slug}/catalog",
        f"/api/v1/public/{slug}/catalog/products",
        f"/api/v1/public/{slug}/catalog/featured",
        f"/api/v1/public/{slug}/catalog/recommended",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert not PRIVATE_WORDS.search(response.text), path
        assert "no-store" not in response.headers.get("cache-control", ""), path

    personalized = client.get(f"/api/v1/public/{slug}/catalog/products", headers={HEADER: secret})
    assert "no-store" in personalized.headers["cache-control"]
    assert HEADER in personalized.headers.get("vary", "")
    assert not PRIVATE_WORDS.search(personalized.text)

    order = client.get("/api/v1/public/order", headers={"X-Order-Reference": reference})
    assert order.status_code == 200
    assert "no-store" in order.headers["cache-control"]
    assert order.headers["x-robots-tag"].startswith("noindex")
    assert not PRIVATE_WORDS.search(order.text), order.text
    assert customer["id"] not in order.text and str(tenant) not in order.text

    # Order/context/invoice ids alone open nothing: the reference or capability is the only key.
    order_id = placed.json()["order_id"]
    assert client.get(f"/api/v1/public/order/{order_id}").status_code == 404
    assert client.get("/api/v1/public/order").status_code == 404
    by_id = client.get("/api/v1/public/order", headers={"X-Order-Reference": order_id})
    assert by_id.status_code == 404
