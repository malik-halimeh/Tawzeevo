"""D-060 provider chain (audit finding TWZ-F-013): OpenRouteService, then Google Maps only when
its key is configured, then the offline heuristic. No network: every provider call is stubbed."""

from __future__ import annotations

import re
from uuid import UUID

import httpx
import pytest

from tawzeevo_api.config import get_settings
from tawzeevo_api.services import routing
from tawzeevo_api.services.routing import (
    GOOGLE_METHOD,
    OFFLINE_METHOD,
    ORS_METHOD,
    Stop,
    offline_order,
    suggest_order,
)

ORIGIN = (33.8938, 35.5018)
STOPS = [
    Stop(UUID(int=1), 33.90, 35.51),
    Stop(UUID(int=2), 33.95, 35.60),
    Stop(UUID(int=3), 33.89, 35.50),
]


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouteservice_api_key", None)
    monkeypatch.setattr(settings, "google_maps_api_key", None)
    yield


def _ors_down(url, json=None, headers=None, timeout=None):
    raise httpx.ConnectError("ors down")


def _google_ok(url, params=None, timeout=None):
    return httpx.Response(
        200,
        json={"status": "OK", "routes": [{"waypoint_order": [1, 2, 0]}]},
        request=httpx.Request("GET", url),
    )


def test_no_keys_means_offline_without_any_network_call(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("no provider may be called without a key")

    monkeypatch.setattr(routing.httpx, "post", never)
    monkeypatch.setattr(routing.httpx, "get", never)
    ordered, method, note = suggest_order(ORIGIN, STOPS)
    assert method == OFFLINE_METHOD and note is None
    assert ordered == offline_order(ORIGIN, STOPS)


def test_google_is_the_fallback_when_ors_fails_and_its_key_is_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouteservice_api_key", "AUDIT_STUB_ORS")
    monkeypatch.setattr(settings, "google_maps_api_key", "AUDIT_STUB_GOOGLE")
    sent: dict = {}

    def google(url, params=None, timeout=None):
        sent.update(url=url, params=params, timeout=timeout)
        return _google_ok(url, params, timeout)

    monkeypatch.setattr(routing.httpx, "post", _ors_down)
    monkeypatch.setattr(routing.httpx, "get", google)
    ordered, method, note = suggest_order(ORIGIN, STOPS)
    assert method == GOOGLE_METHOD
    assert [s.id for s in ordered] == [STOPS[1].id, STOPS[2].id, STOPS[0].id]
    assert note == f"{ORS_METHOD}: ors down unavailable"
    assert (
        sent["url"] == routing.GOOGLE_DIRECTIONS_URL
        and sent["timeout"] == settings.routing_timeout_seconds
    )
    assert sent["params"]["waypoints"].startswith("optimize:true|")
    assert sent["params"]["origin"] == sent["params"]["destination"] == "33.8938,35.5018"
    # Coordinates only: no ids, names or anything but numbers in the waypoint list.
    assert re.fullmatch(
        r"optimize:true(\|-?\d+(\.\d+)?,-?\d+(\.\d+)?)+", sent["params"]["waypoints"]
    )


def test_google_alone_is_used_when_only_its_key_is_configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_maps_api_key", "AUDIT_STUB_GOOGLE")
    monkeypatch.setattr(routing.httpx, "post", _ors_down)  # must not be called
    monkeypatch.setattr(routing.httpx, "get", _google_ok)
    ordered, method, note = suggest_order(ORIGIN, STOPS)
    assert method == GOOGLE_METHOD and note is None
    assert len(ordered) == 3


@pytest.mark.parametrize(
    "answer",
    [
        lambda url: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
        lambda url: httpx.Response(500, json={}, request=httpx.Request("GET", url)),
        lambda url: httpx.Response(
            200,
            json={"status": "OVER_QUERY_LIMIT", "routes": []},
            request=httpx.Request("GET", url),
        ),
        lambda url: httpx.Response(
            200,
            json={"status": "OK", "routes": [{"waypoint_order": [0, 1]}]},
            request=httpx.Request("GET", url),
        ),
        lambda url: httpx.Response(
            200,
            json={"status": "OK", "routes": [{"waypoint_order": [0, 0, 1]}]},
            request=httpx.Request("GET", url),
        ),
        lambda url: httpx.Response(200, json={"nonsense": True}, request=httpx.Request("GET", url)),
    ],
    ids=["timeout", "http-500", "quota", "skipped-stop", "duplicate-stop", "malformed"],
)
def test_every_google_failure_falls_back_to_the_deterministic_offline_order(monkeypatch, answer):
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouteservice_api_key", "AUDIT_STUB_ORS")
    monkeypatch.setattr(settings, "google_maps_api_key", "AUDIT_STUB_GOOGLE")
    monkeypatch.setattr(routing.httpx, "post", _ors_down)
    monkeypatch.setattr(routing.httpx, "get", lambda url, params=None, timeout=None: answer(url))
    first = suggest_order(ORIGIN, STOPS)
    second = suggest_order(ORIGIN, list(reversed(STOPS)))
    assert first[1] == second[1] == OFFLINE_METHOD
    assert first[0] == second[0] == offline_order(ORIGIN, STOPS)  # same input, same order
    assert first[2] and first[2].startswith(
        "provider unavailable: openrouteservice: ors down; google-maps: "
    )


def test_online_disabled_or_no_stops_never_calls_a_provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouteservice_api_key", "AUDIT_STUB_ORS")
    monkeypatch.setattr(settings, "google_maps_api_key", "AUDIT_STUB_GOOGLE")

    def never(*args, **kwargs):
        raise AssertionError("no provider may be called")

    monkeypatch.setattr(routing.httpx, "post", never)
    monkeypatch.setattr(routing.httpx, "get", never)
    assert suggest_order(ORIGIN, STOPS, allow_online=False)[1] == OFFLINE_METHOD
    assert suggest_order(ORIGIN, [])[1] == OFFLINE_METHOD
