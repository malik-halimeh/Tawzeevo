"""Stop-order suggestion (PHASE_07.md F/G; D-060).

Offline: a deterministic heuristic — nearest neighbour from the origin, then 2-opt improvement on
straight-line (haversine) distance. It is labelled `offline stop-order suggestion` and never
claims an optimal road route. Online: OpenRouteService's optimization endpoint through one
adapter, with a timeout; Google Maps Platform (Directions with optimised waypoints) is tried
next, only when its key is configured; any failure falls back to the heuristic, and the answer
names the provider that produced the order plus why the earlier ones were skipped. The payload
sent to a provider holds coordinates only — no names, phones or amounts. Manual reorder always
remains. The map's road line (D-092) comes from OpenRouteService directions through the same key
and timeout; without it the stops are joined by straight lines, labelled as such. The in-site
directions preview (D-093) uses the same endpoint for one leg — the member's position, read once on
request, to one stop — and returns the turn list as neutral codes the app words in EN/AR.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock
from uuid import UUID

import httpx

from tawzeevo_api.config import get_settings

OFFLINE_METHOD = "offline stop-order suggestion"
ORS_METHOD = "openrouteservice"
GOOGLE_METHOD = "google-maps"
ORS_URL = "https://api.openrouteservice.org/optimization"
GOOGLE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
STRAIGHT_METHOD = "straight-line"
ORS_DIRECTIONS_MAX_POINTS = 50  # the provider's waypoint limit per request


@dataclass(frozen=True)
class Stop:
    id: UUID
    latitude: float
    longitude: float


def haversine_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _route_length(origin: tuple[float, float], order: list[Stop]) -> float:
    total = 0.0
    prev_lat, prev_lng = origin
    for stop in order:
        total += haversine_m(prev_lat, prev_lng, stop.latitude, stop.longitude)
        prev_lat, prev_lng = stop.latitude, stop.longitude
    return total


def offline_order(origin: tuple[float, float], stops: list[Stop]) -> list[Stop]:
    """Nearest neighbour, then 2-opt. Ties break on the stop id so two devices with the same
    input produce the same order (PHASE_07.md L "deterministic offline heuristic")."""
    remaining = sorted(stops, key=lambda s: str(s.id))
    order: list[Stop] = []
    cur_lat, cur_lng = origin
    while remaining:
        nearest = min(
            remaining,
            key=lambda s: (
                round(haversine_m(cur_lat, cur_lng, s.latitude, s.longitude), 3),
                str(s.id),
            ),
        )
        remaining.remove(nearest)
        order.append(nearest)
        cur_lat, cur_lng = nearest.latitude, nearest.longitude
    improved = True
    while improved and len(order) > 3:
        improved = False
        best = _route_length(origin, order)
        for i in range(0, len(order) - 2):
            for j in range(i + 2, len(order)):
                candidate = order[: i + 1] + order[i + 1 : j + 1][::-1] + order[j + 1 :]
                length = _route_length(origin, candidate)
                if length < best - 0.5:  # half a metre: ignore floating noise
                    order, best, improved = candidate, length, True
    return order


class RoutingProviderError(Exception):
    pass


def openrouteservice_order(
    origin: tuple[float, float], stops: list[Stop], api_key: str, timeout: float
) -> list[Stop]:
    """ORS optimization (VROOM): one vehicle starting at the origin, one job per stop.
    Coordinates only leave the server (privacy-conscious payload)."""
    by_index = {index + 1: stop for index, stop in enumerate(stops)}
    payload = {
        "jobs": [
            {"id": index, "location": [stop.longitude, stop.latitude]}
            for index, stop in by_index.items()
        ],
        "vehicles": [{"id": 1, "profile": "driving-car", "start": [origin[1], origin[0]]}],
    }
    try:
        response = httpx.post(
            ORS_URL,
            json=payload,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:  # timeout, connection, protocol errors
        raise RoutingProviderError(str(exc)) from exc
    if response.status_code != 200:
        raise RoutingProviderError(f"status {response.status_code}")
    try:
        steps = response.json()["routes"][0]["steps"]
        ordered = [by_index[int(step["job"])] for step in steps if step.get("type") == "job"]
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise RoutingProviderError("unexpected provider response") from exc
    if len(ordered) != len(stops):
        raise RoutingProviderError("provider skipped stops")
    return ordered


def google_maps_order(
    origin: tuple[float, float], stops: list[Stop], api_key: str, timeout: float
) -> list[Stop]:
    """Google Maps Platform Directions with `optimize:true` waypoints: a round trip from the
    origin over every stop; the answer's `waypoint_order` is the visiting order. Coordinates only
    leave the server."""
    point = f"{origin[0]},{origin[1]}"
    params = {
        "origin": point,
        "destination": point,
        "waypoints": "optimize:true|" + "|".join(f"{s.latitude},{s.longitude}" for s in stops),
        "mode": "driving",
        "key": api_key,
    }
    try:
        response = httpx.get(GOOGLE_DIRECTIONS_URL, params=params, timeout=timeout)
    except httpx.HTTPError as exc:
        raise RoutingProviderError(str(exc)) from exc
    if response.status_code != 200:
        raise RoutingProviderError(f"status {response.status_code}")
    try:
        body = response.json()
        if body.get("status") != "OK":
            raise RoutingProviderError(f"status {body.get('status', 'unknown')}")
        order = [stops[int(index)] for index in body["routes"][0]["waypoint_order"]]
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise RoutingProviderError("unexpected provider response") from exc
    if len(order) != len(stops) or len({s.id for s in order}) != len(stops):
        raise RoutingProviderError("provider skipped stops")
    return order


def suggest_order(
    origin: tuple[float, float], stops: list[Stop], *, allow_online: bool = True
) -> tuple[list[Stop], str, str | None]:
    """Returns (ordered stops, method, provider note). The chain is D-060: OpenRouteService,
    then Google Maps, each only when its key is configured, then the offline heuristic; a
    provider failure never fails the call, and the note records every provider that was
    skipped and why, so the fallback is observable and the same input always answers the same
    way for a given configuration."""
    settings = get_settings()
    if not allow_online or not stops:
        return offline_order(origin, stops), OFFLINE_METHOD, None
    timeout = settings.routing_timeout_seconds
    chain: list[tuple[str, str | None, object]] = [
        (ORS_METHOD, settings.openrouteservice_api_key, openrouteservice_order),
        (GOOGLE_METHOD, settings.google_maps_api_key, google_maps_order),
    ]
    skipped: list[str] = []
    for method, api_key, provider in chain:
        if not api_key:
            continue
        try:
            ordered = provider(origin, stops, api_key, timeout)  # type: ignore[operator]
        except RoutingProviderError as exc:
            skipped.append(f"{method}: {exc}")
            continue
        note = "; ".join(skipped) + " unavailable" if skipped else None
        return ordered, method, note
    note = f"provider unavailable: {'; '.join(skipped)}" if skipped else None
    return offline_order(origin, stops), OFFLINE_METHOD, note


def openrouteservice_path(
    points: list[tuple[float, float]], api_key: str, timeout: float
) -> list[tuple[float, float]]:
    """Road geometry through the points in the given order, as (latitude, longitude) pairs.
    Coordinates only leave the server."""
    try:
        response = httpx.post(
            ORS_DIRECTIONS_URL,
            json={
                "coordinates": [[lng, lat] for lat, lng in points],
                "geometry_simplify": True,
                "instructions": False,
            },
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise RoutingProviderError(str(exc)) from exc
    if response.status_code != 200:
        raise RoutingProviderError(f"status {response.status_code}")
    try:
        line = response.json()["features"][0]["geometry"]["coordinates"]
        path = [(round(float(lat), 5), round(float(lng), 5)) for lng, lat, *_ in line]
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise RoutingProviderError("unexpected provider response") from exc
    if len(path) < 2:
        raise RoutingProviderError("empty route")
    return path


@dataclass(frozen=True)
class DirectionStep:
    type: int  # OpenRouteService instruction type: 0 left … 10 arrive, 11 depart, 12/13 keep
    name: str | None
    distance_m: float
    duration_s: float
    exit_number: int | None


@dataclass(frozen=True)
class Directions:
    points: list[tuple[float, float]]
    distance_m: float
    duration_s: float | None
    steps: list[DirectionStep]


def openrouteservice_directions(
    origin: tuple[float, float], destination: tuple[float, float], api_key: str, timeout: float
) -> Directions:
    """One road leg with its turn list. Coordinates only leave the server; the provider's own
    instruction sentences are not used (it has no Arabic), only the step codes and street names."""
    try:
        response = httpx.post(
            ORS_DIRECTIONS_URL,
            json={
                "coordinates": [[origin[1], origin[0]], [destination[1], destination[0]]],
                "instructions": True,
                "units": "m",
            },
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise RoutingProviderError(str(exc)) from exc
    if response.status_code != 200:
        raise RoutingProviderError(f"status {response.status_code}")
    try:
        feature = response.json()["features"][0]
        line = feature["geometry"]["coordinates"]
        summary = feature["properties"]["summary"]
        raw_steps = [
            step for segment in feature["properties"]["segments"] for step in segment["steps"]
        ]
        points = [(round(float(lat), 5), round(float(lng), 5)) for lng, lat, *_ in line]
        steps = [
            DirectionStep(
                type=int(step["type"]),
                name=None if step.get("name") in (None, "", "-") else str(step["name"]),
                distance_m=round(float(step.get("distance", 0)), 1),
                duration_s=round(float(step.get("duration", 0)), 1),
                exit_number=int(step["exit_number"]) if step.get("exit_number") else None,
            )
            for step in raw_steps
        ]
        distance = round(float(summary.get("distance", 0)), 1)
        duration = round(float(summary.get("duration", 0)), 1)
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise RoutingProviderError("unexpected provider response") from exc
    if len(points) < 2:
        raise RoutingProviderError("empty route")
    return Directions(points=points, distance_m=distance, duration_s=duration, steps=steps)


def directions(
    origin: tuple[float, float], destination: tuple[float, float]
) -> tuple[Directions, str]:
    """The directions preview for one leg. Without the provider the answer is the straight line
    and its length, with no drive time and no turns, so it never pretends to be a road route."""
    settings = get_settings()
    api_key = settings.openrouteservice_api_key
    if api_key:
        try:
            found = openrouteservice_directions(
                origin, destination, api_key, settings.routing_timeout_seconds
            )
            return found, ORS_METHOD
        except RoutingProviderError:
            pass
    straight = Directions(
        points=[origin, destination],
        distance_m=round(haversine_m(origin[0], origin[1], destination[0], destination[1]), 1),
        duration_s=None,
        steps=[],
    )
    return straight, STRAIGHT_METHOD


# The same stops in the same order draw the same road line: every page showing the route map asks
# for it, so a provider answer is kept for a while in this process (coordinates only, no names).
PATH_CACHE_SECONDS = 15 * 60
PATH_CACHE_MAX = 256
_path_cache: dict[tuple[tuple[float, float], ...], tuple[float, list[tuple[float, float]]]] = {}
_path_cache_lock = Lock()


def _cached_path(key: tuple[tuple[float, float], ...]) -> list[tuple[float, float]] | None:
    with _path_cache_lock:
        entry = _path_cache.get(key)
        if entry is None or time.monotonic() - entry[0] > PATH_CACHE_SECONDS:
            _path_cache.pop(key, None)
            return None
        return list(entry[1])


def _remember_path(key: tuple[tuple[float, float], ...], path: list[tuple[float, float]]) -> None:
    with _path_cache_lock:
        if len(_path_cache) >= PATH_CACHE_MAX:
            _path_cache.pop(next(iter(_path_cache)))
        _path_cache[key] = (time.monotonic(), list(path))


def clear_path_cache() -> None:
    with _path_cache_lock:
        _path_cache.clear()


def route_path(points: list[tuple[float, float]]) -> tuple[list[tuple[float, float]], str]:
    """The line the map draws through the stops, and how it was made. A provider failure never
    fails the call: the answer falls back to straight lines between the stops."""
    settings = get_settings()
    api_key = settings.openrouteservice_api_key
    if api_key and 2 <= len(points) <= ORS_DIRECTIONS_MAX_POINTS:
        key = tuple((round(lat, 6), round(lng, 6)) for lat, lng in points)
        cached = _cached_path(key)
        if cached is not None:
            return cached, ORS_METHOD
        try:
            path = openrouteservice_path(points, api_key, settings.routing_timeout_seconds)
        except RoutingProviderError:
            return list(points), STRAIGHT_METHOD
        _remember_path(key, path)
        return path, ORS_METHOD
    return list(points), STRAIGHT_METHOD


def as_float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)
