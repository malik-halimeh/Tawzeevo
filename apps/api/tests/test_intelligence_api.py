"""D-089 owner-only intelligence API: owner A sees only A, owner B gets nothing of A, drivers,
the platform admin and anonymous callers are refused, filters stay per currency, no response
carries a cross-currency or forecast field, and repeated calls write nothing."""

from __future__ import annotations

from decimal import Decimal

from test_delivery_tasks import _driver, _get
from test_intelligence_features import canonical_counts, seed_customer_history
from test_invoice_editor import _auth, _login, _owner_context, _user

from tawzeevo_api.models import SystemUserType

ROUTES = (
    "/api/v1/intelligence/priorities",
    "/api/v1/intelligence/inactivity",
    "/api/v1/intelligence/anomalies",
    "/api/v1/intelligence/cash-flow",
)
FORBIDDEN_KEYS = {
    "total",
    "grand_total",
    "fx_converted_total",
    "predicted_cash_balance",
    "expected_payment_date",
    "collection_probability",
    "churn_probability",
    "runway",
}


def _keys(value, found=None):
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, inner in value.items():
            found.add(key)
            _keys(inner, found)
    elif isinstance(value, list):
        for inner in value:
            _keys(inner, found)
    return found


def test_owner_only_tenant_bound_and_read_only(client, session_factory):
    seed = seed_customer_history(client, session_factory, "intapi")
    tenant, token = seed["tenant"], seed["token"]
    _o, tenant_b, token_b = _owner_context(client, session_factory, "intapi2")
    _d, driver_token, _m = _driver(client, session_factory, tenant, "driver-intapi@example.com")
    admin = _user(session_factory, "admin-intapi-x@example.com", SystemUserType.ADMIN)
    admin_token = _login(client, admin.email)

    before = canonical_counts(session_factory)
    bodies = {}
    for route in ROUTES:
        response = _get(client, tenant, token, route)
        assert response.status_code == 200, (route, response.text)
        bodies[route] = response.json()
        assert _get(client, tenant, token, route).status_code == 200
        assert not _keys(bodies[route]) & FORBIDDEN_KEYS, route
        # Refusals: another business's owner, a driver, the platform admin, anonymous.
        assert _get(client, tenant, token_b, route).status_code == 403
        assert _get(client, tenant, driver_token, route).status_code == 403
        assert _get(client, tenant, admin_token, route).status_code == 403
        assert client.get(f"{route}?tenant_id={tenant}").status_code == 401
        # Owner B's own view of its empty business contains nothing of A.
        own = _get(client, tenant_b, token_b, route)
        assert own.status_code == 200
        assert seed["customer"]["id"] not in own.text and seed["customer"]["name"] not in own.text
    assert canonical_counts(session_factory) == before  # GETs never write business rows

    priorities = bodies["/api/v1/intelligence/priorities"]
    assert [g["currency"] for g in priorities["groups"]] == ["LBP", "USD"]
    top = priorities["groups"][1]["items"][0]
    assert top["customer_id"] == seed["customer"]["id"] and top["currency"] == "USD"
    assert top["suggested_action_code"] == "COLLECT_OVERDUE"
    assert set(top["components"]) == {
        "collection_urgency",
        "relationship_inactivity",
        "activity_decline",
        "friction_signals",
    }
    assert top["components"]["activity_decline"] is None  # unavailable, not zero
    assert Decimal(top["outstanding_balance"]) > 0

    inactivity = bodies["/api/v1/intelligence/inactivity"]
    usd = next(g for g in inactivity["groups"] if g["currency"] == "USD")
    mine = next(i for i in usd["items"] if i["customer_id"] == seed["customer"]["id"])
    assert mine["status"] == "WATCH" and Decimal(mine["recency_ratio"]) == Decimal("1.5")

    anomalies = bodies["/api/v1/intelligence/anomalies"]
    assert (
        anomalies["window"]["timezone"] == "Asia/Beirut" and anomalies["window"]["block_days"] == 7
    )

    cash = bodies["/api/v1/intelligence/cash-flow"]
    assert cash["period"]["key"] == "90d"
    usd_cash = next(c for c in cash["currencies"] if c["currency"] == "USD")
    assert usd_cash["planned_collections"]["projection_warning_code"] == (
        "DELIVERY_PROJECTION_IGNORES_ADJUSTMENTS"
    )


def _query(client, tenant, token, path, **params):
    return client.get(path, params={"tenant_id": tenant, **params}, headers=_auth(token))


def test_filters_and_validation(client, session_factory):
    seed = seed_customer_history(client, session_factory, "intapif")
    tenant, token = seed["tenant"], seed["token"]
    base = "/api/v1/intelligence"
    only_usd = _query(client, tenant, token, f"{base}/priorities", currency="USD", limit=1)
    assert only_usd.status_code == 200
    groups = only_usd.json()["groups"]
    assert [g["currency"] for g in groups] == ["USD"] and len(groups[0]["items"]) == 1
    watch = _query(client, tenant, token, f"{base}/inactivity", status="WATCH").json()
    assert {i["status"] for g in watch["groups"] for i in g["items"]} == {"WATCH"}
    typed = _query(client, tenant, token, f"{base}/anomalies", type="OVERDUE_THRESHOLD_CROSSED")
    assert typed.status_code == 200
    lbp = _query(client, tenant, token, f"{base}/cash-flow", currency="LBP", period="30d")
    assert [c["currency"] for c in lbp.json()["currencies"]] == ["LBP"]
    for route, params in (
        ("priorities", {"currency": "usd"}),
        ("priorities", {"limit": 0}),
        ("inactivity", {"status": "CHURNED"}),
        ("anomalies", {"type": "FRAUD"}),
        ("cash-flow", {"period": "7d"}),
        ("cash-flow", {"planned_days": 90}),
    ):
        assert _query(client, tenant, token, f"{base}/{route}", **params).status_code == 422
