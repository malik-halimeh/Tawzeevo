"""D-109: the platform tenant list filters by access state on the server."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from test_invoice_editor import _auth, _login, _owner_context, _user

from tawzeevo_api.models import SystemUserType, Tenant


def test_access_status_filter_current_grace_overdue(client, session_factory):
    ids = {}
    for name in ("current", "grace", "overdue"):
        _owner, tenant, _token = _owner_context(client, session_factory, f"acc{name}")
        ids[name] = tenant
    today = date.today()
    with session_factory() as db:
        grace = db.get(Tenant, UUID(ids["grace"]))
        overdue = db.get(Tenant, UUID(ids["overdue"]))
        assert grace is not None and overdue is not None
        grace.access_until, grace.grace_until = today - timedelta(days=2), today + timedelta(days=3)
        overdue.access_until, overdue.grace_until = (
            today - timedelta(days=9),
            today - timedelta(days=1),
        )
        db.commit()
    admin = _user(session_factory, "admin-access@example.com", SystemUserType.ADMIN)
    token = _login(client, admin.email)

    def listed(state: str) -> set[str]:
        response = client.get(
            "/api/v1/platform/tenants",
            headers=_auth(token),
            params={"access_status": state, "limit": 100},
        )
        assert response.status_code == 200, response.text
        rows = response.json()["tenants"]
        assert all(row["access_status"] == state for row in rows)
        assert response.json()["total"] == len(rows)
        return {row["id"] for row in rows}

    assert ids["current"] in listed("current")
    assert listed("grace") >= {ids["grace"]} and ids["current"] not in listed("grace")
    assert ids["overdue"] in listed("overdue") and ids["grace"] not in listed("overdue")
    bad = client.get(
        "/api/v1/platform/tenants", headers=_auth(token), params={"access_status": "late"}
    )
    assert bad.status_code == 422
