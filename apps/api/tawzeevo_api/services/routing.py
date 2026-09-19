"""Stop-order suggestion (PHASE_07.md F/G; D-060).

Offline: a deterministic heuristic — nearest neighbour from the origin, then 2-opt improvement on
straight-line (haversine) distance. It is labelled `offline stop-order suggestion` and never
claims an optimal road route. Online: OpenRouteService's optimization endpoint through one
adapter, with a timeout and any failure falling back to the heuristic; Google Maps only when its
key is configured (adapter slot, not exercised by tests). The payload sent to a provider holds
coordinates only — no names, phones or amounts. Manual reorder always remains.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

import httpx

from tawzeevo_api.config import get_settings

OFFLINE_METHOD = "offline stop-order suggestion"
ORS_METHOD = "openrouteservice"
ORS_URL = "https://api.openrouteservice.org/optimization"


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


def suggest_order(
    origin: tuple[float, float], stops: list[Stop], *, allow_online: bool = True
) -> tuple[list[Stop], str, str | None]:
    """Returns (ordered stops, method, provider note). Provider failure never fails the call."""
    settings = get_settings()
    if allow_online and settings.openrouteservice_api_key and stops:
        try:
            return (
                openrouteservice_order(
                    origin,
                    stops,
                    settings.openrouteservice_api_key,
                    settings.routing_timeout_seconds,
                ),
                ORS_METHOD,
                None,
            )
        except RoutingProviderError as exc:
            return offline_order(origin, stops), OFFLINE_METHOD, f"provider unavailable: {exc}"
    return offline_order(origin, stops), OFFLINE_METHOD, None


def as_float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)
