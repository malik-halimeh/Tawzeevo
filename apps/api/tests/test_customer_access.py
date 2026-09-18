"""P5-M3: personalized customer storefront links (D-071, D-072, D-075, D-076)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from sqlalchemy import func, select
from test_invoice_editor import _auth, _catalog, _login, _owner_context, _user
from test_storefront import _publish, _slug

from tawzeevo_api.models import AuditEvent, CustomerAccessLink, SystemUserType, Tenant

HEADER = "X-Customer-Capability"


def _issue(client, tenant, token, customer_id):
    r = client.post(
        f"/api/v1/tenants/{tenant}/customers/{customer_id}/access-link", headers=_auth(token)
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["storefront_path"].startswith(f"/{_slug_of(client, tenant, token)}/access#")
    return body, body["storefront_path"].split("#", 1)[1]


def _slug_of(client, tenant, token):
    return client.get(f"/api/v1/tenants/{tenant}/storefront", headers=_auth(token)).json()["slug"]


def _catalog_prices(client, slug, secret=None):
    headers = {HEADER: secret} if secret else {}
    r = client.get(f"/api/v1/public/{slug}/catalog/products", headers=headers)
    assert r.status_code == 200, r.text
    return r, {row["name"]: (row["price"], row["pricing"]) for row in r.json()["items"]}


def test_link_gives_current_customer_pricing_without_exposing_anything_private(
    client, session_factory, caplog
):
    _owner, tenant, token = _owner_context(client, session_factory, "plink")
    category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    # Customer is grade A; a 20 % grade discount applies to grade A.
    assert client.put(
        f"/api/v1/tenants/{tenant}/grade-discounts/A",
        headers=_auth(token),
        json={"discount_percent": "20.00"},
    ).status_code in (200, 201)

    anonymous, public_prices = _catalog_prices(client, slug)
    assert public_prices["Cedar Water"] == (product["unit_price"], "public")
    assert anonymous.headers["cache-control"].startswith("public")

    with caplog.at_level(logging.INFO):
        issued, secret = _issue(client, tenant, token, customer["id"])
    assert issued["last_used_at"] is None and issued["rotated_from_id"] is None
    # The context endpoint knows the display name and the assurance, nothing else.
    context = client.get("/api/v1/public/customer-context", headers={HEADER: secret})
    assert context.status_code == 200, context.text
    assert context.json() == {"assurance": "LINK", "tenant_slug": slug, "display_name": customer["name"]}
    assert context.headers["cache-control"] == "no-store"
    for forbidden in ("grade", "balance", "debt", "phone", "invoice", "payment"):
        assert forbidden not in context.text.lower()

    personalized, prices = _catalog_prices(client, slug, secret)
    assert prices["Cedar Water"] == ("10.0000", "personalized")  # 12.5000 minus 20 %
    assert personalized.headers["cache-control"] == "private, no-store"
    assert "grade" not in personalized.text.lower()
    # Explicit grade price for this product overrides the discount; a grade change follows the
    # customer identity immediately, without a new link (D-071).
    assert client.put(
        f"/api/v1/tenants/{tenant}/products/{product['id']}/grade-prices/A",
        headers=_auth(token),
        json={"unit_price": "9.0000"},
    ).status_code in (200, 201)
    assert _catalog_prices(client, slug, secret)[1]["Cedar Water"][0] == "9.0000"
    assert client.put(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}",
        headers=_auth(token),
        json={"grade": "B"},
    ).status_code == 200
    assert _catalog_prices(client, slug, secret)[1]["Cedar Water"] == (product["unit_price"], "personalized")
    # Featured/recommended/detail honour the same context; the secret never reaches the logs.
    detail = client.get(f"/api/v1/public/{slug}/catalog/products/{product['id']}", headers={HEADER: secret})
    assert detail.json()["pricing"] == "personalized"
    assert secret not in caplog.text and secret.split(".")[1] not in caplog.text
    with session_factory() as db:
        stored = db.scalar(select(CustomerAccessLink))
        assert stored is not None and stored.token_sha256 != secret and secret not in stored.token_sha256
        assert stored.expires_at is None, "no automatic expiry (D-071)"
        assert stored.last_used_at is not None, "context resolution records last use"


def test_rotation_revocation_one_active_and_isolation(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "plink-life")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)
    other = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": "Other Shop", "phone": "+96170123777", "grade": "A"},
    ).json()

    first, secret_a = _issue(client, tenant, token, customer["id"])
    status = client.get(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(token)).json()
    assert status["active"]["id"] == first["id"] and status["effective_policy"] == "LINK"
    assert status["available_policies"] == ["LINK"]

    # Rotation: the old secret dies the instant the new one exists; only one active row.
    second, secret_b = _issue(client, tenant, token, customer["id"])
    assert second["rotated_from_id"] == first["id"]
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret_a}).status_code == 404
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret_b}).status_code == 200
    assert _catalog_prices(client, slug, secret_a)[1]["Cedar Water"][1] == "public", "a rotated link is anonymous"
    with session_factory() as db:
        active = db.scalar(select(func.count()).select_from(CustomerAccessLink).where(CustomerAccessLink.revoked_at.is_(None)))
        assert active == 1
        assert db.scalar(select(CustomerAccessLink).where(CustomerAccessLink.id == UUID(first["id"]))).revoked_reason == "rotated"

    # Customer A's link never resolves Customer B: contexts are bound to the exact customer.
    _other_link, secret_other = _issue(client, tenant, token, other["id"])
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret_other}).json()["display_name"] == "Other Shop"
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret_b}).json()["display_name"] == customer["name"]

    # Revocation without replacement; a second revoke is a 404; garbage secrets are 404 too.
    revoked = client.delete(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(token))
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret_b}).status_code == 404
    assert client.delete(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(token)).status_code == 404
    for bad in ("", "nonsense", secret_b[:-1] + "x", f"{uuid4().hex}.{'a' * 43}"):
        r = client.get("/api/v1/public/customer-context", headers={HEADER: bad})
        assert r.status_code == 404 and r.json()["detail"]["code"] == "CUSTOMER_LINK_UNAVAILABLE"

    # Another business cannot issue or read links for this customer; policies stay LINK-only.
    _o2, other_tenant, other_token = _owner_context(client, session_factory, "plink-b")
    assert client.post(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(other_token)).status_code == 403
    assert client.post(f"/api/v1/tenants/{other_tenant}/customers/{customer['id']}/access-link", headers=_auth(other_token)).status_code == 404
    for policy in ("VERIFIED", "ACCOUNT_REQUIRED"):
        r = client.put(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-policy", headers=_auth(token), json={"override": policy})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "ACCESS_POLICY_NOT_AVAILABLE"
        assert client.put(f"/api/v1/tenants/{tenant}/storefront/access-policy", headers=_auth(token), json={"policy": policy}).status_code == 409
    assert client.put(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-policy", headers=_auth(token), json={"override": "nope"}).status_code == 422
    ok = client.put(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-policy", headers=_auth(token), json={"override": "LINK"})
    assert ok.status_code == 200 and ok.json()["policy_override"] == "LINK"
    with session_factory() as db:
        actions = sorted(db.scalars(select(AuditEvent.action).where(AuditEvent.tenant_id == UUID(tenant), AuditEvent.action.like("customer_%"))))
        assert {"customer_link_issued", "customer_link_rotated", "customer_link_revoked", "customer_access_policy_changed"} <= set(actions)


def test_suspended_business_and_concurrent_issuance(client, session_factory):
    _owner, tenant, token = _owner_context(client, session_factory, "plink-susp")
    _category, product, customer = _catalog(client, tenant, token, name="Cedar Water")
    _publish(client, tenant, token, product["id"])
    slug = _slug(session_factory, tenant)

    # Concurrent issuance for the same customer: exactly one active link survives.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(f"/api/v1/tenants/{tenant}/customers/{customer['id']}/access-link", headers=_auth(token)), range(4)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CustomerAccessLink).where(CustomerAccessLink.revoked_at.is_(None))) == 1
        assert db.scalar(select(func.count()).select_from(CustomerAccessLink)) == 4
    live = [r.json()["storefront_path"].split("#")[1] for r in results]
    alive = [s for s in live if client.get("/api/v1/public/customer-context", headers={HEADER: s}).status_code == 200]
    assert len(alive) == 1
    secret = alive[0]

    # Tenant suspension: the link resolves to nothing while suspended, and works again after.
    admin = _user(session_factory, "plink.admin@example.com", SystemUserType.ADMIN)
    admin_token = _login(client, admin.email)
    assert client.post(f"/api/v1/platform/tenants/{tenant}/suspend", headers=_auth(admin_token), json={"reason": "SUBSCRIPTION_OVERDUE"}).status_code == 200
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret}).status_code == 404
    assert _catalog_prices(client, slug, secret)[1]["Cedar Water"][1] == "public"
    assert client.post(f"/api/v1/platform/tenants/{tenant}/reactivate", headers=_auth(admin_token), json={}).status_code == 200
    assert client.get("/api/v1/public/customer-context", headers={HEADER: secret}).status_code == 200
    with session_factory() as db:
        row = db.get(Tenant, UUID(tenant))
        assert row is not None and row.customer_access_policy == "LINK"
