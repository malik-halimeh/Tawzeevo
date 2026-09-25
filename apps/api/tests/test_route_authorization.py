"""Route authorization inventory and deny-cell probes (audit finding TWZ-F-008; D-022; D-007).

Every route operation the API exposes must carry an explicit authorization expectation here, and
that expectation must match the dependency the route actually resolves through. A new route
without an entry, a route whose dependency was widened, or a route without any authorization
dependency outside the known public prefixes fails this module. The deny cells (anonymous,
client without membership, another tenant's owner, a driver, the platform admin) are then probed
at runtime for every non-public route: a resource may be missing (fresh ids), but the answer must
already be the authorization refusal, never the resource's own status.

The 12-resource matrix in test_security_matrix.py keeps proving the allow cells with real data;
this module proves that no route escapes the matrix.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from test_auth import login, register
from test_delivery_tasks import _driver
from test_invoice_editor import _auth, _owner_context
from test_platform import create_user, token

from tawzeevo_api.main import app
from tawzeevo_api.models import SystemUserType

PUBLIC = "PUBLIC"
AUTHENTICATED = "AUTHENTICATED"
CLIENT = "CLIENT"
ADMIN = "ADMIN"
TENANT_MEMBER = "TENANT_MEMBER"
TENANT_OWNER = "TENANT_OWNER"

# Dependency name -> class, most specific first (an owner route also resolves the member and
# user dependencies underneath it).
DEPENDENCY_CLASSES = (
    ("require_tenant_owner", TENANT_OWNER),
    ("require_system_admin", ADMIN),
    ("require_client", CLIENT),
    ("get_tenant_context", TENANT_MEMBER),
    ("get_current_user", AUTHENTICATED),
    ("get_auth_context", AUTHENTICATED),
)

# Paths that may exist without an authorization dependency: capability/link-bearing public
# surfaces, unauthenticated auth entry points, health and the Phase 1 public statistics.
PUBLIC_PREFIXES = (
    "/health",
    "/stats/",
    "/login",
    "/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/password/",
    "/api/v1/public/",
)

EXPECTED: dict[str, str] = {
    "GET /api/v1/analytics/customers/{customer_id}": "TENANT_OWNER",
    "GET /api/v1/analytics/events": "TENANT_OWNER",
    "GET /api/v1/analytics/invoices/{invoice_id}": "TENANT_OWNER",
    "GET /api/v1/analytics/overview": "TENANT_OWNER",
    "GET /api/v1/intelligence/anomalies": "TENANT_OWNER",
    "GET /api/v1/intelligence/cash-flow": "TENANT_OWNER",
    "GET /api/v1/intelligence/copilot/status": "TENANT_OWNER",
    "GET /api/v1/intelligence/inactivity": "TENANT_OWNER",
    "GET /api/v1/intelligence/priorities": "TENANT_OWNER",
    "POST /api/v1/auth/logout": "AUTHENTICATED",
    "POST /api/v1/auth/password/forgot": "PUBLIC",
    "POST /api/v1/auth/password/reset": "PUBLIC",
    "POST /api/v1/auth/refresh": "PUBLIC",
    "GET /api/v1/customer-ledger/customers/{customer_id}/balances": "TENANT_OWNER",
    "GET /api/v1/customer-ledger/debts": "TENANT_OWNER",
    "POST /api/v1/customer-ledger/opening-balances": "TENANT_OWNER",
    "POST /api/v1/customer-ledger/opening-balances/{entry_id}/correct": "TENANT_OWNER",
    "GET /api/v1/customer-ledger/settings": "TENANT_OWNER",
    "PUT /api/v1/customer-ledger/settings": "TENANT_OWNER",
    "GET /api/v1/delivery-tasks": "TENANT_OWNER",
    "POST /api/v1/delivery-tasks": "TENANT_OWNER",
    "GET /api/v1/delivery-tasks/eligible-invoices": "TENANT_OWNER",
    "GET /api/v1/delivery-tasks/my-work": "TENANT_MEMBER",
    "GET /api/v1/delivery-tasks/{task_id}": "TENANT_OWNER",
    "PATCH /api/v1/delivery-tasks/{task_id}": "TENANT_OWNER",
    "PUT /api/v1/delivery-tasks/{task_id}/assignee": "TENANT_OWNER",
    "POST /api/v1/delivery-tasks/{task_id}/cancel": "TENANT_OWNER",
    "POST /api/v1/delivery-tasks/{task_id}/complete": "TENANT_MEMBER",
    "POST /api/v1/delivery-tasks/{task_id}/location": "TENANT_MEMBER",
    "POST /api/v1/intelligence/copilot/query": "TENANT_OWNER",
    "POST /api/v1/intelligence/explain": "TENANT_OWNER",
    "POST /api/v1/invoices": "TENANT_OWNER",
    "POST /api/v1/invoices/calculator": "TENANT_OWNER",
    "GET /api/v1/invoices/catalog-search": "TENANT_OWNER",
    "POST /api/v1/invoices/item-parser": "TENANT_OWNER",
    "GET /api/v1/invoices/products/{product_id}/cost-options": "TENANT_OWNER",
    "GET /api/v1/invoices/{invoice_id}": "TENANT_OWNER",
    "PUT /api/v1/invoices/{invoice_id}": "TENANT_OWNER",
    "POST /api/v1/invoices/{invoice_id}/cancel": "TENANT_OWNER",
    "GET /api/v1/invoices/{invoice_id}/capabilities": "TENANT_OWNER",
    "POST /api/v1/invoices/{invoice_id}/capabilities": "TENANT_OWNER",
    "DELETE /api/v1/invoices/{invoice_id}/capabilities/{capability_id}": "TENANT_OWNER",
    "POST /api/v1/invoices/{invoice_id}/capabilities/{capability_id}/rotate": "TENANT_OWNER",
    "POST /api/v1/invoices/{invoice_id}/confirm": "TENANT_OWNER",
    "GET /api/v1/invoices/{invoice_id}/history": "TENANT_OWNER",
    "POST /api/v1/payments/customer-receipts": "TENANT_OWNER",
    "POST /api/v1/payments/customer-refunds": "TENANT_OWNER",
    "GET /api/v1/payments/customers/{customer_id}/obligations": "TENANT_OWNER",
    "POST /api/v1/payments/supplier-payments": "TENANT_OWNER",
    "POST /api/v1/payments/supplier-payments/{payment_id}/reverse": "TENANT_OWNER",
    "POST /api/v1/payments/supplier-prepayments": "TENANT_OWNER",
    "POST /api/v1/payments/{payment_id}/reverse": "TENANT_OWNER",
    "GET /api/v1/platform/tenant-applications": "ADMIN",
    "POST /api/v1/platform/tenant-applications/{application_id}/approve": "ADMIN",
    "POST /api/v1/platform/tenant-applications/{application_id}/reject": "ADMIN",
    "GET /api/v1/platform/tenants": "ADMIN",
    "PUT /api/v1/platform/tenants/{tenant_id}/access-period": "ADMIN",
    "POST /api/v1/platform/tenants/{tenant_id}/backups/{backup_id}/import": "ADMIN",
    "POST /api/v1/platform/tenants/{tenant_id}/close": "ADMIN",
    "POST /api/v1/platform/tenants/{tenant_id}/reactivate": "ADMIN",
    "POST /api/v1/platform/tenants/{tenant_id}/suspend": "ADMIN",
    "GET /api/v1/procurement/assignees": "TENANT_OWNER",
    "GET /api/v1/procurement/lists": "TENANT_OWNER",
    "POST /api/v1/procurement/lists": "TENANT_OWNER",
    "GET /api/v1/procurement/lists/{list_id}": "TENANT_OWNER",
    "PUT /api/v1/procurement/lists/{list_id}/assignee": "TENANT_OWNER",
    "POST /api/v1/procurement/lists/{list_id}/cancel": "TENANT_OWNER",
    "POST /api/v1/procurement/lists/{list_id}/carry-forward": "TENANT_OWNER",
    "POST /api/v1/procurement/lists/{list_id}/complete": "TENANT_OWNER",
    "GET /api/v1/procurement/lists/{list_id}/export.csv": "TENANT_OWNER",
    "POST /api/v1/procurement/lists/{list_id}/items": "TENANT_OWNER",
    "PATCH /api/v1/procurement/lists/{list_id}/items/{item_id}": "TENANT_OWNER",
    "POST /api/v1/procurement/lists/{list_id}/items/{item_id}/remove": "TENANT_OWNER",
    "POST /api/v1/procurement/lists/{list_id}/items/{item_id}/waive": "TENANT_OWNER",
    "GET /api/v1/procurement/my-pickups": "TENANT_MEMBER",
    "GET /api/v1/public/customer-context": "PUBLIC",
    "POST /api/v1/public/customer-verification/confirm": "PUBLIC",
    "GET /api/v1/public/customer-verification/dev-code": "PUBLIC",
    "DELETE /api/v1/public/customer-verification/session": "PUBLIC",
    "POST /api/v1/public/customer-verification/start": "PUBLIC",
    "GET /api/v1/public/invoice": "PUBLIC",
    "GET /api/v1/public/invoice/data": "PUBLIC",
    "GET /api/v1/public/invoice/qr": "PUBLIC",
    "GET /api/v1/public/order": "PUBLIC",
    "POST /api/v1/public/order/cancellation-request": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/branding/logo": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/catalog": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/catalog/featured": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/catalog/images/{kind}/{image_id}": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/catalog/products": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/catalog/products/{product_id}": "PUBLIC",
    "POST /api/v1/public/{tenant_slug}/catalog/products/{product_id}/view": "PUBLIC",
    "GET /api/v1/public/{tenant_slug}/catalog/recommended": "PUBLIC",
    "POST /api/v1/public/{tenant_slug}/checkout": "PUBLIC",
    "GET /api/v1/routes/nearby-suppliers": "TENANT_MEMBER",
    "PUT /api/v1/routes/order": "TENANT_MEMBER",
    "POST /api/v1/routes/suggest-order": "TENANT_MEMBER",
    "POST /api/v1/supplier-ledger/opening-balances": "TENANT_OWNER",
    "POST /api/v1/supplier-ledger/opening-balances/{entry_id}/correct": "TENANT_OWNER",
    "GET /api/v1/supplier-ledger/totals": "TENANT_OWNER",
    "GET /api/v1/supplier-ledger/{supplier_id}/balances": "TENANT_OWNER",
    "GET /api/v1/supplier-prices/products/{product_id}": "TENANT_OWNER",
    "GET /api/v1/supplier-prices/products/{product_id}/recommendation": "TENANT_OWNER",
    "GET /api/v1/supplier-purchases": "TENANT_OWNER",
    "POST /api/v1/supplier-purchases": "TENANT_OWNER",
    "GET /api/v1/supplier-purchases/{purchase_id}": "TENANT_OWNER",
    "POST /api/v1/supplier-purchases/{purchase_id}/reverse": "TENANT_OWNER",
    "GET /api/v1/suppliers": "TENANT_OWNER",
    "POST /api/v1/suppliers": "TENANT_OWNER",
    "GET /api/v1/suppliers/products/{product_id}/costs": "TENANT_OWNER",
    "POST /api/v1/suppliers/products/{product_id}/costs": "TENANT_OWNER",
    "PUT /api/v1/suppliers/products/{product_id}/preferred-supplier": "TENANT_OWNER",
    "PATCH /api/v1/suppliers/{supplier_id}": "TENANT_OWNER",
    "POST /api/v1/sync/bootstrap": "TENANT_MEMBER",
    "GET /api/v1/sync/bootstrap/{collection}": "TENANT_MEMBER",
    "GET /api/v1/sync/pull": "TENANT_MEMBER",
    "POST /api/v1/sync/push": "TENANT_MEMBER",
    "POST /api/v1/tenant-applications": "CLIENT",
    "GET /api/v1/tenant-contexts": "AUTHENTICATED",
    "GET /api/v1/tenants/{tenant_id}/backup": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/backup/google/authorize": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/backup/google/connect": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/backup/google/disconnect": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/backup/run": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/backup/{backup_id}/verify": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/branding": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/branding": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/branding/logo": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/catalog/barcodes/{barcode}": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/categories": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/categories": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/categories/{category_id}": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/categories/{category_id}": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/categories/{category_id}/archive": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/customers": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/customers/search": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/customers/{customer_id}": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/customers/{customer_id}": "TENANT_OWNER",
    "DELETE /api/v1/tenants/{tenant_id}/customers/{customer_id}/access-link": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/customers/{customer_id}/access-link": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/customers/{customer_id}/access-link": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/customers/{customer_id}/access-policy": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/customers/{customer_id}/verified-sessions/revoke": (
        "TENANT_OWNER"
    ),
    "GET /api/v1/tenants/{tenant_id}/grade-discounts": "TENANT_OWNER",
    "DELETE /api/v1/tenants/{tenant_id}/grade-discounts/{grade}": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/grade-discounts/{grade}": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/invoices": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/invoices/{invoice_id}": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/memberships": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/memberships": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/memberships/{membership_id}/revoke": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/notifications": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/notifications/{notification_id}/read": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/orders": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/orders/cancellation-requests/{request_id}/decide": (
        "TENANT_OWNER"
    ),
    "GET /api/v1/tenants/{tenant_id}/orders/{order_id}": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/orders/{order_id}/confirm": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/orders/{order_id}/decline": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/orders/{order_id}/delivery-date": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/orders/{order_id}/link-customer": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/product-images/{ownership}/{image_id}/content": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/products": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/products": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/products/barcode/{barcode}": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/products/{product_id}": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/products/{product_id}": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/products/{product_id}/barcodes": "TENANT_OWNER",
    "DELETE /api/v1/tenants/{tenant_id}/products/{product_id}/grade-prices/{grade}": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/products/{product_id}/grade-prices/{grade}": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/products/{product_id}/images": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/products/{product_id}/pricing": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/storefront": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/storefront/access-policy": "TENANT_OWNER",
    "GET /api/v1/tenants/{tenant_id}/storefront/campaigns": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/storefront/campaigns": "TENANT_OWNER",
    "POST /api/v1/tenants/{tenant_id}/storefront/campaigns/{campaign_id}/cancel": "TENANT_OWNER",
    "PUT /api/v1/tenants/{tenant_id}/storefront/slug": "TENANT_OWNER",
    "GET /health": "PUBLIC",
    "GET /health/database": "PUBLIC",
    "GET /health/metrics": "PUBLIC",
    "POST /login": "PUBLIC",
    "POST /register": "PUBLIC",
    "GET /stats/average-age": "PUBLIC",
    "GET /stats/count": "PUBLIC",
    "GET /stats/platform": "PUBLIC",
    "GET /stats/top-cities": "PUBLIC",
    "GET /users": "ADMIN",
    "POST /users": "ADMIN",
    "GET /users/me": "AUTHENTICATED",
    "PUT /users/me": "AUTHENTICATED",
    "DELETE /users/{user_id}": "ADMIN",
    "PUT /users/{user_id}": "ADMIN",
}


def _walk(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif type(route).__name__ == "_IncludedRouter":
            yield from _walk(route.original_router.routes)


def _dependency_names(dependant, out: set[str]) -> set[str]:
    for sub in dependant.dependencies:
        if sub.call is not None:
            out.add(getattr(sub.call, "__name__", repr(sub.call)))
        _dependency_names(sub, out)
    return out


def route_inventory() -> dict[str, str]:
    """'METHOD path' -> authorization class resolved from the route's dependency tree."""
    inventory: dict[str, str] = {}
    for route in _walk(app.routes):
        names = _dependency_names(route.dependant, set())
        resolved = PUBLIC
        for dependency, klass in DEPENDENCY_CLASSES:
            if dependency in names:
                resolved = klass
                break
        for method in route.methods:
            inventory[f"{method} {route.path}"] = resolved
    return inventory


def test_every_route_has_an_explicit_expectation_that_matches_its_dependency():
    inventory = route_inventory()
    unregistered = sorted(set(inventory) - set(EXPECTED))
    stale = sorted(set(EXPECTED) - set(inventory))
    assert unregistered == [], f"routes without an authorization expectation: {unregistered}"
    assert stale == [], f"expectations for routes that no longer exist: {stale}"
    mismatched = {
        key: (EXPECTED[key], resolved)
        for key, resolved in inventory.items()
        if EXPECTED[key] != resolved
    }
    assert mismatched == {}, f"declared vs resolved authorization: {mismatched}"
    assert len(inventory) >= 180


def test_public_routes_live_only_under_the_known_public_prefixes():
    stray = sorted(
        key
        for key, klass in route_inventory().items()
        if klass == PUBLIC and not key.split(" ", 1)[1].startswith(PUBLIC_PREFIXES)
    )
    assert stray == [], (
        f"routes without an authorization dependency outside public prefixes: {stray}"
    )


_PATH_VALUES = {
    "grade": "A",
    "barcode": "5280000000001",
    "kind": "product",
    "ownership": "tenant",
    "collection": "customers",
    "tenant_slug": "nobody",
}


def _url(key: str, tenant_id: str) -> tuple[str, str]:
    method, path = key.split(" ", 1)

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        if name == "tenant_id":
            return tenant_id
        return _PATH_VALUES.get(name, str(uuid4()))

    url = re.sub(r"\{([a-z_]+)\}", fill, path)
    if "{tenant_id}" not in path:
        url += f"?tenant_id={tenant_id}"
    return method, url


def _probe(client, key: str, tenant_id: str, headers: dict[str, str] | None) -> int:
    method, url = _url(key, tenant_id)
    kwargs: dict[str, object] = {"headers": headers or {}}
    if method in ("POST", "PUT", "PATCH"):
        kwargs["json"] = {}
    return client.request(method, url, **kwargs).status_code


@pytest.fixture
def actors(client, session_factory):
    _owner, tenant_a, owner_a = _owner_context(client, session_factory, "authz-a")
    _o2, _tenant_b, owner_b = _owner_context(client, session_factory, "authz-b")
    _user, driver_a, _membership = _driver(
        client, session_factory, tenant_a, "authz-driver@example.com"
    )
    register(client)
    plain_client = str(login(client)["access_token"])
    admin_user = create_user(session_factory, "authz-admin@example.com", SystemUserType.ADMIN)
    return {
        "tenant_a": tenant_a,
        "owner_a": owner_a,
        "owner_b": owner_b,
        "driver_a": driver_a,
        "client": plain_client,
        "admin": token(client, admin_user.email),
    }


def _protected(*classes: str) -> list[str]:
    return sorted(key for key, klass in EXPECTED.items() if klass in classes)


def test_anonymous_requests_are_refused_on_every_protected_route(client, actors):
    wrong = {
        key: status
        for key in _protected(AUTHENTICATED, CLIENT, ADMIN, TENANT_MEMBER, TENANT_OWNER)
        if (status := _probe(client, key, actors["tenant_a"], None)) != 401
    }
    assert wrong == {}, f"anonymous not refused with 401: {wrong}"


def test_a_client_without_membership_is_refused_on_admin_and_tenant_routes(client, actors):
    headers = _auth(actors["client"])
    wrong = {
        key: status
        for key in _protected(ADMIN, TENANT_MEMBER, TENANT_OWNER)
        if (status := _probe(client, key, actors["tenant_a"], headers)) != 403
    }
    assert wrong == {}, f"client without membership not refused with 403: {wrong}"


def test_another_tenants_owner_is_refused_on_tenant_and_admin_routes(client, actors):
    headers = _auth(actors["owner_b"])
    wrong = {
        key: status
        for key in _protected(ADMIN, TENANT_MEMBER, TENANT_OWNER)
        if (status := _probe(client, key, actors["tenant_a"], headers)) != 403
    }
    assert wrong == {}, f"other tenant's owner not refused with 403: {wrong}"


def test_a_driver_is_refused_on_owner_only_and_admin_routes(client, actors):
    headers = _auth(actors["driver_a"])
    wrong = {
        key: status
        for key in _protected(TENANT_OWNER, ADMIN)
        if (status := _probe(client, key, actors["tenant_a"], headers)) != 403
    }
    assert wrong == {}, f"driver not refused with 403: {wrong}"


def test_the_platform_admin_never_reaches_tenant_or_client_routes(client, actors):
    headers = _auth(actors["admin"])
    wrong = {
        key: status
        for key in _protected(TENANT_MEMBER, TENANT_OWNER, CLIENT)
        if (status := _probe(client, key, actors["tenant_a"], headers)) != 403
    }
    assert wrong == {}, f"platform admin not refused with 403 on tenant/client routes: {wrong}"
