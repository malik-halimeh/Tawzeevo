"""Phase 7 P7-M3: location precedence (D-061), deterministic offline stop order and provider
fallback (D-060), nearby supplier reminder with role projection (PHASE_07.md E/F/G/H)."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import httpx
from test_delivery_tasks import _driver, _get, _post
from test_invoice_editor import _attach_latest_cost, _auth, _catalog, _owner_context
from test_procurement import _confirm_invoice, _today

from tawzeevo_api.config import get_settings
from tawzeevo_api.services import routing
from tawzeevo_api.services.routing import Stop, offline_order


def _task_for(
    client, session_factory, owner, tenant, token, product, name, phone, lat, lng, assignee=None
):
    customer = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": name, "phone": phone, "latitude": lat, "longitude": lng},
    ).json()
    confirmed = _confirm_invoice(client, tenant, token, customer["id"], product["id"], "1")
    body = {"invoice_id": confirmed["id"]}
    if assignee:
        body["assigned_membership_id"] = assignee
    created = _post(client, tenant, token, "/api/v1/delivery-tasks", body)
    assert created.status_code == 201, created.text
    return created.json(), customer


def test_offline_heuristic_is_deterministic_and_improves_on_input_order():
    origin = (33.8938, 35.5018)  # Beirut
    stops = [
        Stop(UUID(int=1), 33.8886, 35.4955),
        Stop(UUID(int=2), 33.9000, 35.5100),
        Stop(UUID(int=3), 33.8800, 35.4800),
        Stop(UUID(int=4), 33.8950, 35.5050),
        Stop(UUID(int=5), 33.9100, 35.5200),
    ]
    first = offline_order(origin, stops)
    again = offline_order(origin, list(reversed(stops)))
    assert [s.id for s in first] == [s.id for s in again]  # input order does not matter
    assert routing._route_length(origin, first) <= routing._route_length(origin, stops)
    assert first[0].id == UUID(int=4)  # nearest to the origin comes first


def test_location_precedence_never_overwrites_confirmed_or_better_readings(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p7loc")
    _category, product, _customer = _catalog(client, tenant, token, name="Water")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    _d, driver_token, driver_membership = _driver(
        client, session_factory, tenant, "driver-p7loc@example.com"
    )
    task, customer = _task_for(
        client,
        session_factory,
        owner,
        tenant,
        token,
        product,
        "Shop A",
        "+96170100001",
        "33.900000",
        "35.500000",
        assignee=driver_membership,
    )
    path = f"/api/v1/delivery-tasks/{task['id']}/location"

    # Existing manual reading; a good GPS reading from the assigned driver replaces it.
    gps = _post(
        client,
        tenant,
        driver_token,
        path,
        {
            "latitude": "33.900500",
            "longitude": "35.500500",
            "source": "gps",
            "accuracy_meters": "12",
        },
    )
    assert gps.status_code == 200, gps.text
    assert gps.json()["applied"] is True and gps.json()["location"]["source"] == "gps"
    # A worse reading (loose GPS, or manual) does not silently replace the good GPS one.
    loose = _post(
        client,
        tenant,
        driver_token,
        path,
        {
            "latitude": "33.910000",
            "longitude": "35.510000",
            "source": "gps",
            "accuracy_meters": "250",
        },
    )
    assert loose.json()["applied"] is False and loose.json()["reason"] == "BETTER_READING_KEPT"
    manual = _post(
        client,
        tenant,
        token,
        path,
        {"latitude": "33.920000", "longitude": "35.520000", "source": "manual"},
    )
    assert manual.json()["applied"] is False
    assert manual.json()["location"]["latitude"] == "33.900500"
    # Operator confirmation wins and then nothing unconfirmed can replace it.
    confirmed = _post(
        client,
        tenant,
        driver_token,
        path,
        {
            "latitude": "33.900600",
            "longitude": "35.500600",
            "source": "gps",
            "accuracy_meters": "8",
            "confirm": True,
        },
    )
    assert (
        confirmed.json()["reason"] == "CONFIRMED" and confirmed.json()["location"]["confirmed_at"]
    )
    better_gps = _post(
        client,
        tenant,
        driver_token,
        path,
        {
            "latitude": "33.900700",
            "longitude": "35.500700",
            "source": "gps",
            "accuracy_meters": "3",
        },
    )
    assert (
        better_gps.json()["applied"] is False
        and better_gps.json()["reason"] == "CONFIRMED_LOCATION_KEPT"
    )
    reconfirm = _post(
        client,
        tenant,
        token,
        path,
        {"latitude": "33.900800", "longitude": "35.500800", "source": "manual", "confirm": True},
    )
    assert (
        reconfirm.json()["applied"] is True
        and reconfirm.json()["location"]["latitude"] == "33.900800"
    )
    # Another driver may not touch it; no history is kept (single reading per customer).
    _d2, other_token, _m2 = _driver(client, session_factory, tenant, "driver-p7loc2@example.com")
    assert (
        _post(
            client, tenant, other_token, path, {"latitude": "1", "longitude": "1", "source": "gps"}
        ).status_code
        == 403
    )
    row = client.get(
        f"/api/v1/tenants/{tenant}/customers/{customer['id']}", headers=_auth(token)
    ).json()
    assert row["latitude"] == "33.900800"


def test_suggest_order_uses_provider_when_configured_and_falls_back_on_failure(
    client, session_factory, monkeypatch
):
    owner, tenant, token = _owner_context(client, session_factory, "p7route")
    _category, product, _customer = _catalog(client, tenant, token, name="Bread")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    far, _ = _task_for(
        client,
        session_factory,
        owner,
        tenant,
        token,
        product,
        "Far",
        "+96170200001",
        "33.950000",
        "35.600000",
    )
    near, _ = _task_for(
        client,
        session_factory,
        owner,
        tenant,
        token,
        product,
        "Near",
        "+96170200002",
        "33.895000",
        "35.503000",
    )
    mid, _ = _task_for(
        client,
        session_factory,
        owner,
        tenant,
        token,
        product,
        "Mid",
        "+96170200003",
        "33.910000",
        "35.530000",
    )
    nowhere = client.post(
        f"/api/v1/tenants/{tenant}/customers",
        headers=_auth(token),
        json={"name": "Nowhere", "phone": "+96170200004"},
    ).json()
    lost = _post(
        client,
        tenant,
        token,
        "/api/v1/delivery-tasks",
        {
            "invoice_id": _confirm_invoice(
                client, tenant, token, nowhere["id"], product["id"], "1"
            )["id"]
        },
    ).json()
    ids = [far["id"], near["id"], mid["id"], lost["id"]]
    body = {"origin": {"latitude": "33.893800", "longitude": "35.501800"}, "task_ids": ids}

    # No key: offline heuristic, labelled, unlocated stops appended at the end.
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouteservice_api_key", None)
    offline = _post(client, tenant, token, "/api/v1/routes/suggest-order", body)
    assert offline.status_code == 200, offline.text
    assert offline.json()["method"] == "offline stop-order suggestion"
    assert [s["customer_name"] for s in offline.json()["stops"]] == [
        "Near",
        "Mid",
        "Far",
        "Nowhere",
    ]
    assert offline.json()["unlocated_task_ids"] == [lost["id"]]

    # Provider success: order comes from the provider, payload carried coordinates only.
    monkeypatch.setattr(settings, "openrouteservice_api_key", "test-key")
    sent: dict = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"], sent["json"], sent["timeout"] = url, json, timeout
        steps = (
            [{"type": "start"}]
            + [{"type": "job", "job": job_id} for job_id in (3, 1, 2)]
            + [{"type": "end"}]
        )
        return httpx.Response(200, json={"routes": [{"steps": steps}]})

    monkeypatch.setattr(routing.httpx, "post", fake_post)
    online = _post(client, tenant, token, "/api/v1/routes/suggest-order", body)
    assert online.status_code == 200 and online.json()["method"] == "openrouteservice"
    assert [s["customer_name"] for s in online.json()["stops"]] == ["Mid", "Far", "Near", "Nowhere"]
    assert sent["timeout"] == settings.routing_timeout_seconds
    assert not re.search(r"Far|Near|Mid|\+96170", str(sent["json"]))  # privacy: coordinates only

    # Provider timeout: silently back to the heuristic with a note; the call never fails.
    def timing_out(url, json=None, headers=None, timeout=None):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(routing.httpx, "post", timing_out)
    fallback = _post(client, tenant, token, "/api/v1/routes/suggest-order", body)
    assert (
        fallback.status_code == 200 and fallback.json()["method"] == "offline stop-order suggestion"
    )
    assert "provider unavailable" in (fallback.json()["note"] or "")
    monkeypatch.setattr(settings, "openrouteservice_api_key", None)

    # Manual reorder persists as route_sequence and shows in My Work; closed tasks refused.
    saved = client.put(
        f"/api/v1/routes/order?tenant_id={tenant}",
        headers=_auth(token),
        json={"task_ids": [mid["id"], near["id"], far["id"], lost["id"]]},
    )
    assert saved.status_code == 200, saved.text
    work = _get(client, tenant, token, "/api/v1/delivery-tasks/my-work").json()
    assert [(t["customer_name"], t["route_sequence"]) for t in work["tasks"]] == [
        ("Mid", 1),
        ("Near", 2),
        ("Far", 3),
        ("Nowhere", 4),
    ]
    _post(
        client,
        tenant,
        token,
        f"/api/v1/delivery-tasks/{far['id']}/complete",
        {"expected_version": work["tasks"][2]["version"]},
    )
    closed = client.put(
        f"/api/v1/routes/order?tenant_id={tenant}",
        headers=_auth(token),
        json={"task_ids": [far["id"]]},
    )
    assert closed.status_code == 409


def test_nearby_supplier_reminder_respects_role_and_price_privacy(client, session_factory):
    owner, tenant, token = _owner_context(client, session_factory, "p7near")
    _category, product, customer = _catalog(client, tenant, token, name="Olive Oil")
    _attach_latest_cost(session_factory, owner, tenant, product["id"])
    supplier = _post(
        client,
        tenant,
        token,
        "/api/v1/suppliers",
        {"name": "Zahle Mill", "latitude": "33.846000", "longitude": "35.902000"},
    ).json()
    cost = _post(
        client,
        tenant,
        token,
        f"/api/v1/suppliers/products/{product['id']}/costs",
        {"supplier_id": supplier["id"], "unit_cost": "6", "currency": "USD", "cost_basis": "PIECE"},
    )
    assert cost.status_code == 201, cost.text
    client.put(
        f"/api/v1/suppliers/products/{product['id']}/preferred-supplier?tenant_id={tenant}",
        headers=_auth(token),
        json={"supplier_id": supplier["id"]},
    )
    _confirm_invoice(client, tenant, token, customer["id"], product["id"], "5")
    procurement = _post(
        client,
        tenant,
        token,
        "/api/v1/procurement/lists",
        {"demand_from": _today(), "demand_to": _today()},
    ).json()
    _d, driver_token, driver_membership = _driver(
        client, session_factory, tenant, "driver-p7near@example.com"
    )

    near = "/api/v1/routes/nearby-suppliers"
    here = f"{near}?tenant_id={tenant}&latitude=33.8465&longitude=35.9025&radius_meters=1500"
    owner_view = client.get(here, headers=_auth(token))
    assert owner_view.status_code == 200, owner_view.text
    assert [s["supplier_name"] for s in owner_view.json()["suppliers"]] == ["Zahle Mill"]
    assert owner_view.json()["suppliers"][0]["distance_meters"] < 200
    assert owner_view.json()["suppliers"][0]["items"][0]["remaining_quantity"] == "5.0000"
    far_away = client.get(
        f"{near}?tenant_id={tenant}&latitude=33.89&longitude=35.50&radius_meters=1500",
        headers=_auth(token),
    )
    assert far_away.json()["suppliers"] == []

    # Driver: nothing until the list is assigned to them; then identity/need only, no price.
    assert client.get(here, headers=_auth(driver_token)).json()["suppliers"] == []
    client.put(
        f"/api/v1/procurement/lists/{procurement['id']}/assignee?tenant_id={tenant}",
        headers=_auth(token),
        json={"membership_id": driver_membership},
    )
    driver_view = client.get(here, headers=_auth(driver_token))
    assert driver_view.status_code == 200 and len(driver_view.json()["suppliers"]) == 1
    assert not re.search(r"cost|unit_price|estimate|margin|currency", driver_view.text, re.I)
    assert str(uuid4()) not in driver_view.text
