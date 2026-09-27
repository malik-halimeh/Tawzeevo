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
    routing.clear_path_cache()
    yield
    routing.clear_path_cache()


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


# D-092: the map's road line.
PATH_POINTS = [(33.8966, 35.4823), (33.2733, 35.2036), (33.8058, 35.6)]


def test_route_path_without_a_key_joins_the_stops_with_straight_lines(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("no provider may be called without a key")

    monkeypatch.setattr(routing.httpx, "post", never)
    assert routing.route_path(PATH_POINTS) == (PATH_POINTS, routing.STRAIGHT_METHOD)


def test_route_path_uses_road_geometry_and_sends_coordinates_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")
    sent: dict = {}

    def directions(url, json=None, headers=None, timeout=None):
        sent["url"], sent["json"] = url, json
        line = [[35.4823, 33.8966], [35.3, 33.5, 12.0], [35.6, 33.8058]]
        return httpx.Response(200, json={"features": [{"geometry": {"coordinates": line}}]})

    monkeypatch.setattr(routing.httpx, "post", directions)
    path, method = routing.route_path(PATH_POINTS)
    assert method == ORS_METHOD
    # (latitude, longitude) pairs; an elevation value is dropped
    assert path == [(33.8966, 35.4823), (33.5, 35.3), (33.8058, 35.6)]
    assert sent["url"] == routing.ORS_DIRECTIONS_URL
    assert sent["json"]["coordinates"] == [[lng, lat] for lat, lng in PATH_POINTS]
    assert set(sent["json"]) == {"coordinates", "geometry_simplify", "instructions"}


def test_route_path_keeps_a_provider_line_for_the_same_stops(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")
    calls: list[int] = []

    def directions(url, json=None, headers=None, timeout=None):
        calls.append(1)
        line = [[35.4823, 33.8966], [35.6, 33.8058]]
        return httpx.Response(200, json={"features": [{"geometry": {"coordinates": line}}]})

    monkeypatch.setattr(routing.httpx, "post", directions)
    first = routing.route_path(PATH_POINTS)
    again = routing.route_path(PATH_POINTS)
    assert first == again and first[1] == ORS_METHOD
    assert len(calls) == 1  # the second page view reuses the answer
    routing.route_path(list(reversed(PATH_POINTS)))  # another order is another line
    assert len(calls) == 2


def test_route_path_does_not_keep_a_straight_line_fallback(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")
    answers = [httpx.ReadTimeout("slow")]

    def flaky(url, json=None, headers=None, timeout=None):
        if answers:
            raise answers.pop()
        line = [[35.4823, 33.8966], [35.6, 33.8058]]
        return httpx.Response(200, json={"features": [{"geometry": {"coordinates": line}}]})

    monkeypatch.setattr(routing.httpx, "post", flaky)
    assert routing.route_path(PATH_POINTS)[1] == routing.STRAIGHT_METHOD
    assert routing.route_path(PATH_POINTS)[1] == ORS_METHOD  # the provider is asked again


@pytest.mark.parametrize("failure", ["down", "status", "garbage"])
def test_route_path_falls_back_to_straight_lines_when_the_provider_fails(monkeypatch, failure):
    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")

    def broken(url, json=None, headers=None, timeout=None):
        if failure == "down":
            raise httpx.ReadTimeout("slow")
        if failure == "status":
            return httpx.Response(429, json={})
        return httpx.Response(200, json={"features": []})

    monkeypatch.setattr(routing.httpx, "post", broken)
    assert routing.route_path(PATH_POINTS) == (PATH_POINTS, routing.STRAIGHT_METHOD)


def test_route_path_with_one_stop_or_too_many_never_calls_the_provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")

    def never(*args, **kwargs):
        raise AssertionError("not called")

    monkeypatch.setattr(routing.httpx, "post", never)
    assert routing.route_path(PATH_POINTS[:1])[1] == routing.STRAIGHT_METHOD
    many = [(33.0 + i / 100, 35.0) for i in range(routing.ORS_DIRECTIONS_MAX_POINTS + 1)]
    assert routing.route_path(many) == (many, routing.STRAIGHT_METHOD)


# D-093: the in-site directions preview for one leg.
def test_directions_word_nothing_and_send_coordinates_only(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")
    sent: dict = {}

    def leg(url, json=None, headers=None, timeout=None):
        sent["json"] = json
        body = {
            "features": [
                {
                    "geometry": {"coordinates": [[35.5157, 33.8886], [35.6178, 33.9808]]},
                    "properties": {
                        "summary": {"distance": 17445.8, "duration": 992.5},
                        "segments": [
                            {
                                "steps": [
                                    {"type": 11, "name": "-", "distance": 38.6, "duration": 6.9},
                                    {
                                        "type": 7,
                                        "name": "Charles Helou",
                                        "distance": 900,
                                        "duration": 60,
                                        "exit_number": 2,
                                        "instruction": "provider wording is not used",
                                    },
                                    {"type": 10, "name": "", "distance": 0, "duration": 0},
                                ]
                            }
                        ],
                    },
                }
            ]
        }
        return httpx.Response(200, json=body)

    monkeypatch.setattr(routing.httpx, "post", leg)
    found, method = routing.directions((33.8886, 35.5157), (33.9808, 35.6178))
    assert method == ORS_METHOD
    assert (found.distance_m, found.duration_s) == (17445.8, 992.5)
    assert found.points == [(33.8886, 35.5157), (33.9808, 35.6178)]
    assert [(s.type, s.name, s.exit_number) for s in found.steps] == [
        (11, None, None),
        (7, "Charles Helou", 2),
        (10, None, None),
    ]
    assert sent["json"]["coordinates"] == [[35.5157, 33.8886], [35.6178, 33.9808]]
    assert set(sent["json"]) == {"coordinates", "instructions", "units"}


def test_directions_without_the_provider_are_the_straight_line_and_its_length(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("no provider may be called without a key")

    monkeypatch.setattr(routing.httpx, "post", never)
    found, method = routing.directions((33.8886, 35.5157), (33.9808, 35.6178))
    assert method == routing.STRAIGHT_METHOD
    assert found.points == [(33.8886, 35.5157), (33.9808, 35.6178)]
    assert found.duration_s is None and found.steps == []
    assert 13_000 < found.distance_m < 14_000  # straight-line metres, never a drive time

    monkeypatch.setattr(get_settings(), "openrouteservice_api_key", "test-key")
    monkeypatch.setattr(routing.httpx, "post", _ors_down)
    assert routing.directions((33.8886, 35.5157), (33.9808, 35.6178))[1] == routing.STRAIGHT_METHOD
