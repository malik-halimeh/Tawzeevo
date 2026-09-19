"""Phase 9 P9-M1 (PHASE_09.md B): one authorization matrix over system role × tenant role ×
resource, executed against the real routes. Every cell is an expectation the product contract
already states; the matrix exists so a future route cannot quietly widen access.

Actors: anonymous; a registered client with no membership; a driver of tenant A; the owner of
tenant A; the owner of tenant B (cross-tenant); the platform administrator (lifecycle manager,
never a silent viewer of tenant-private data)."""

from __future__ import annotations

from test_delivery_tasks import _driver
from test_invoice_editor import _auth, _login, _owner_context, _user

from tawzeevo_api.models import SystemUserType

ACTORS = ("anon", "client", "driver", "owner", "other", "admin")
BOOTSTRAP = {
    "device_installation_id": "11111111-1111-1111-1111-111111111111",
    "protocol_version": 1,
    "app_schema_version": 1,
}
# (label, method, path template, body, expected per actor in ACTORS order).
# 200 = any 2xx; 401 = no identity; 403 = identity without authority.
OWNER_ONLY = (401, 403, 403, 200, 403, 403)
MEMBER = (401, 403, 200, 200, 403, 403)
ADMIN_ONLY = (401, 403, 403, 403, 403, 200)
MATRIX = [
    ("analytics overview", "GET", "/api/v1/analytics/overview?tenant_id={a}", None, OWNER_ONLY),
    ("branding read", "GET", "/api/v1/tenants/{a}/branding", None, OWNER_ONLY),
    ("branding write", "PUT", "/api/v1/tenants/{a}/branding", {"banner_text": "x"}, OWNER_ONLY),
    (
        "customers search",
        "GET",
        "/api/v1/tenants/{a}/customers/search?phone=%2B96170123456",
        None,
        OWNER_ONLY,
    ),
    ("suppliers list", "GET", "/api/v1/suppliers?tenant_id={a}", None, OWNER_ONLY),
    ("procurement lists", "GET", "/api/v1/procurement/lists?tenant_id={a}", None, OWNER_ONLY),
    ("delivery tasks", "GET", "/api/v1/delivery-tasks?tenant_id={a}", None, OWNER_ONLY),
    ("delivery my-work", "GET", "/api/v1/delivery-tasks/my-work?tenant_id={a}", None, MEMBER),
    ("team list", "GET", "/api/v1/tenants/{a}/memberships", None, OWNER_ONLY),
    ("sync bootstrap", "POST", "/api/v1/sync/bootstrap?tenant_id={a}", BOOTSTRAP, MEMBER),
    ("platform tenants", "GET", "/api/v1/platform/tenants", None, ADMIN_ONLY),
    ("platform users", "GET", "/users", None, ADMIN_ONLY),
]


def _actors(client, session_factory):
    _owner, tenant_a, owner_token = _owner_context(client, session_factory, "matrix-a")
    _other_owner, tenant_b, other_token = _owner_context(client, session_factory, "matrix-b")
    _d, driver_token, _m = _driver(client, session_factory, tenant_a, "driver-matrix@example.com")
    _user(session_factory, "client-matrix@example.com", SystemUserType.CLIENT)
    tokens = {
        "anon": None,
        "client": _login(client, "client-matrix@example.com"),
        "driver": driver_token,
        "owner": owner_token,
        "other": other_token,
        "admin": _login(client, "admin-matrix-a@example.com"),
    }
    return tenant_a, tenant_b, tokens


def test_authorization_matrix(client, session_factory):
    """Every (resource, actor) cell in one run; all mismatches are reported together."""
    tenant_a, _tenant_b, tokens = _actors(client, session_factory)
    mismatches: list[str] = []
    for label, method, template, body, expectations in MATRIX:
        path = template.format(a=tenant_a)
        for actor, expected in zip(ACTORS, expectations, strict=True):
            token = tokens[actor]
            headers = _auth(token) if token else {}
            response = client.request(method, path, headers=headers, json=body)
            allowed = 200 <= response.status_code < 300
            wrong = (expected == 200) != allowed
            if expected != 200 and response.status_code != expected:
                wrong = True
            if wrong:
                mismatches.append(
                    f"{label} / {actor}: expected {expected}, got {response.status_code}"
                )
            if actor == "other" and not allowed:
                assert tenant_a not in response.text  # never echo another business's identifier
    assert mismatches == [], "; ".join(mismatches)


def test_suspended_tenant_locks_every_member_and_reactivation_restores(client, session_factory):
    _owner, tenant, owner_token = _owner_context(client, session_factory, "matrix-susp")
    _d, driver_token, _m = _driver(client, session_factory, tenant, "driver-susp@example.com")
    admin_token = _login(client, "admin-matrix-susp@example.com")
    overview = f"/api/v1/analytics/overview?tenant_id={tenant}"
    my_work = f"/api/v1/delivery-tasks/my-work?tenant_id={tenant}"
    assert client.get(overview, headers=_auth(owner_token)).status_code == 200
    suspended = client.post(
        f"/api/v1/platform/tenants/{tenant}/suspend", headers=_auth(admin_token)
    )
    assert suspended.status_code == 200, suspended.text
    for token in (owner_token, driver_token):
        denied = client.get(my_work, headers=_auth(token))
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "TENANT_SUSPENDED"
    assert (
        client.get(f"/api/v1/tenants/{tenant}/branding", headers=_auth(owner_token)).status_code
        == 403
    )
    reactivated = client.post(
        f"/api/v1/platform/tenants/{tenant}/reactivate", headers=_auth(admin_token)
    )
    assert reactivated.status_code == 200, reactivated.text
    assert client.get(overview, headers=_auth(owner_token)).status_code == 200
