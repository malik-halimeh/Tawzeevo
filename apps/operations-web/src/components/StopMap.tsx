import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { createBaseMap, tokenColour } from "./mapKit";

/**
 * Route map (D-092): open stops as numbered pins in the saved stop order and the line joining
 * them — road geometry from the server when the routing provider answers, otherwise straight
 * dashed lines that say so. Map images come from MapTiler with the app's browser key; without a
 * key (local development only) OpenStreetMap's tiles are used. Nothing here reads the device
 * position: the map shows saved customer locations only.
 */
export interface MapStop { taskId: string; number: number; name: string; latitude: string | null; longitude: string | null }
export interface MapRoute { key: string; label?: string; stops: MapStop[] }
interface RoutePath { method: string; points: [number, number][] }

/** One colour per route (owner view with several people); the first is the brand route blue. */
const ROUTE_COLOURS = ["var(--blue)", "var(--good)", "var(--warn)", "var(--bad)", "var(--ink-soft)"];

// The same stops in the same order draw the same line: ask the server once per page view.
const pathCache = new Map<string, Promise<RoutePath>>();

const located = (stop: MapStop) => stop.latitude !== null && stop.longitude !== null;
const point = (stop: MapStop): L.LatLngTuple => [Number(stop.latitude), Number(stop.longitude)];

function routePath(tenantId: string, stops: MapStop[]): Promise<RoutePath> {
  const key = `${tenantId}|${stops.map((stop) => `${stop.taskId}@${stop.latitude},${stop.longitude}`).join(";")}`;
  let pending = pathCache.get(key);
  if (!pending) {
    pending = apiRequest<RoutePath>(`/api/v1/routes/path?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ task_ids: stops.map((stop) => stop.taskId) }) });
    pending.catch(() => pathCache.delete(key)); // a failed request is retried on the next view
    pathCache.set(key, pending);
  }
  return pending;
}

export function StopMap({ tenantId, routes, selectedId, onSelect }: { tenantId: string; routes: MapRoute[]; selectedId?: string | undefined; onSelect?: (taskId: string) => void }) {
  const { t } = useTranslation();
  const holder = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const pins = useRef<L.LayerGroup | null>(null);
  const lines = useRef<L.LayerGroup | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;
  const [methods, setMethods] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!holder.current) return undefined;
    const created = createBaseMap(holder.current);
    lines.current = L.layerGroup().addTo(created);
    pins.current = L.layerGroup().addTo(created);
    map.current = created;
    return () => { created.remove(); map.current = null; };
  }, []);

  // Fit the view when the set of stops changes, not when another stop is selected.
  const placesKey = routes.map((route) => route.stops.filter(located).map((stop) => `${stop.latitude},${stop.longitude}`).join(";")).join("|");
  useEffect(() => {
    const places = routes.flatMap((route) => route.stops.filter(located).map(point));
    if (!map.current || places.length === 0) return;
    map.current.invalidateSize(); // the holder may have been laid out after the map was created
    if (places.length === 1) map.current.setView(places[0]!, 14);
    else map.current.fitBounds(L.latLngBounds(places), { paddingTopLeft: [28, 28], paddingBottomRight: [28, 44], maxZoom: 14 });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- placesKey is the stable form of routes' positions
  }, [placesKey]);

  useEffect(() => {
    const group = pins.current;
    if (!group) return;
    group.clearLayers();
    routes.forEach((route, index) => {
      const colour = ROUTE_COLOURS[index % ROUTE_COLOURS.length]!;
      for (const stop of route.stops.filter(located)) {
        const selected = stop.taskId === selectedId;
        const icon = L.divIcon({ className: "map-pin-holder", html: `<span class="map-pin${selected ? " selected" : ""}" style="--pin:${colour}">${stop.number}</span>`, iconSize: [30, 30], iconAnchor: [15, 15] });
        const marker = L.marker(point(stop), { icon, title: `${stop.number}. ${stop.name}`, alt: `${stop.number}. ${stop.name}`, keyboard: true, zIndexOffset: selected ? 1000 : 0 });
        marker.on("click", () => select.current?.(stop.taskId));
        group.addLayer(marker);
      }
    });
  }, [routes, selectedId]);

  useEffect(() => {
    const group = lines.current;
    if (!group) return undefined;
    let current = true;
    group.clearLayers();
    routes.forEach((route, index) => {
      const stops = route.stops.filter(located);
      if (stops.length < 2) return;
      const colour = tokenColour(holder.current ?? document.body, ROUTE_COLOURS[index % ROUTE_COLOURS.length]!, "#2455d6");
      routePath(tenantId, stops).then((path) => {
        if (!current) return;
        const road = path.method !== "straight-line";
        L.polyline(path.points, { color: colour, weight: road ? 4 : 3, opacity: 0.8, dashArray: road ? undefined : "6 8", interactive: false }).addTo(group);
        setMethods((known) => (known[route.key] === path.method ? known : { ...known, [route.key]: path.method }));
      }).catch(() => undefined); // the pins are still useful without a line
    });
    return () => { current = false; };
  }, [routes, tenantId]);

  const unlocated = routes.reduce((count, route) => count + route.stops.filter((stop) => !located(stop)).length, 0);
  const drawn = routes.map((route) => methods[route.key]).filter((method): method is string => Boolean(method));
  return (
    <figure className="stop-map">
      <div aria-label={t("routeMap.label")} className="stop-map-canvas" ref={holder} role="region" />
      <figcaption className="muted">
        {drawn.length === 0 ? t("routeMap.pins") : drawn.every((method) => method !== "straight-line") ? t("routeMap.road") : t("routeMap.straight")}
        {unlocated ? ` · ${t("routeMap.unlocated", { count: unlocated })}` : ""}
      </figcaption>
      {routes.length > 1 ? (
        <ul className="stop-map-legend" aria-label={t("routeMap.legend")}>
          {routes.map((route, index) => <li key={route.key}><span aria-hidden="true" className="map-swatch" style={{ background: ROUTE_COLOURS[index % ROUTE_COLOURS.length] }} />{route.label}</li>)}
        </ul>
      ) : null}
    </figure>
  );
}
