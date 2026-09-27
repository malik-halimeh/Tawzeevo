import L from "leaflet";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { type DirectionsResult, distanceText, durationText, stepText } from "./directions";
import { createBaseMap, tokenColour } from "./mapKit";

/**
 * In-site directions preview (D-093): from the member's position — read once when they press
 * Directions, never stored or followed — to one stop, on the app's own map with distance, drive
 * time and the turn list. The server words nothing: step codes and street names come back and are
 * worded here in EN/AR. Without the routing provider it is the straight line and its length.
 */
function DirectionsMap({ points }: { points: [number, number][] }) {
  const { t } = useTranslation();
  const holder = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!holder.current || points.length < 2) return undefined;
    const map = createBaseMap(holder.current);
    const colour = tokenColour(holder.current, "var(--blue)", "#2455d6");
    L.polyline(points, { color: colour, weight: 5, opacity: 0.85, interactive: false }).addTo(map);
    L.circleMarker(points[0]!, { radius: 7, color: "#fff", weight: 2, fillColor: colour, fillOpacity: 1 }).addTo(map);
    L.marker(points[points.length - 1]!, { icon: L.divIcon({ className: "map-pin-holder", html: '<span class="map-pin selected" style="--pin:var(--blue)">●</span>', iconSize: [30, 30], iconAnchor: [15, 15] }), keyboard: false, interactive: false }).addTo(map);
    map.invalidateSize();
    map.fitBounds(L.latLngBounds(points), { paddingTopLeft: [24, 24], paddingBottomRight: [24, 40], maxZoom: 16 });
    return () => { map.remove(); };
  }, [points]);
  return <div aria-label={t("directions.mapLabel")} className="stop-map-canvas directions-canvas" ref={holder} role="region" />;
}

export function DirectionsView({ result, onClose }: { result: DirectionsResult; onClose: () => void }) {
  const { t } = useTranslation();
  const road = result.method !== "straight-line";
  return (
    <section aria-labelledby="directions-title" className="directions">
      <div className="row">
        <h3 id="directions-title">{t("directions.title", { customer: result.customer })}</h3>
        <button className="text-button" onClick={onClose} type="button">{t("directions.hide")}</button>
      </div>
      <DirectionsMap points={result.points} />
      <p className="directions-summary">
        <strong>{distanceText(t, result.distance_m)}</strong>
        {road && result.duration_s !== null ? <> · {t("directions.about", { time: durationText(t, result.duration_s) })}</> : null}
      </p>
      <p className="muted">{road ? t("directions.fromHere") : t("directions.straight")}</p>
      {result.steps.length ? (
        <ol className="directions-steps" aria-label={t("directions.steps")}>
          {result.steps.map((step, index) => (
            <li key={index}>
              <span>{stepText(t, step, result.customer)}</span>
              {step.type !== 10 && step.distance_m > 0 ? <small className="muted">{t("directions.then", { distance: distanceText(t, step.distance_m) })}</small> : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
