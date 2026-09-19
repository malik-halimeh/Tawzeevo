import { useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis } from "../api/types";
import { ErrorState } from "./Ui";

/**
 * Stop-order planning, location correction and the nearby-supplier reminder (PHASE_07.md E/F/G/H;
 * D-060, D-061). Shared by the owner's Deliveries screen and the member's My Work screen. The
 * position is read once, on request, from the browser — never tracked continuously.
 */
interface Stop { task_id: string; sequence: number; customer_name: string; latitude: string | null; longitude: string | null; has_location: boolean }
interface Suggestion { method: string; note: string | null; stops: Stop[]; unlocated_task_ids: string[] }
interface NearbyItem { product_name: string; remaining_quantity: string; price_basis: ProductPriceBasis; pieces_per_box: number | null; list_title: string }
interface Nearby { radius_meters: number; suppliers: { supplier_id: string; supplier_name: string; contact_phone: string | null; address: string | null; latitude: string; longitude: string; distance_meters: number; items: NearbyItem[] }[] }
interface LocationResult { applied: boolean; reason: string; location: { latitude: string | null; longitude: string | null; source: string | null; accuracy_meters: string | null; confirmed_at: string | null } }
export interface RouteTask { id: string; customer_name: string; version: number }

function currentPosition(): Promise<{ latitude: number; longitude: number; accuracy: number } | null> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) { resolve(null); return; }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    );
  });
}

export function RoutePlanner({ tenantId, tasks, onSaved }: { tenantId: string; tasks: RouteTask[]; onSaved?: () => void }) {
  const { t } = useTranslation();
  const q = `?tenant_id=${tenantId}`;
  const [suggestion, setSuggestion] = useState<Suggestion>();
  const [order, setOrder] = useState<Stop[]>([]);
  const [nearby, setNearby] = useState<Nearby>();
  const [confirmLocation, setConfirmLocation] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const run = (action: () => Promise<string | undefined>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    action().then((message) => { if (message) setNotice(message); }).catch(setError).finally(() => setBusy(false));
  };
  const suggest = () => run(async () => {
    const here = await currentPosition();
    const body = await apiRequest<Suggestion>(`/api/v1/routes/suggest-order${q}`, { method: "POST", body: JSON.stringify({ origin: here ? { latitude: here.latitude.toFixed(6), longitude: here.longitude.toFixed(6) } : null, task_ids: tasks.map((task) => task.id) }) });
    setSuggestion(body); setOrder(body.stops);
    return here ? undefined : t("route.noPosition");
  });
  const move = (index: number, delta: number) => {
    const next = [...order];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target]!, next[index]!];
    setOrder(next.map((stop, i) => ({ ...stop, sequence: i + 1 })));
  };
  const save = () => run(async () => {
    await apiRequest(`/api/v1/routes/order${q}`, { method: "PUT", body: JSON.stringify({ task_ids: order.map((stop) => stop.task_id) }) });
    onSaved?.();
    return t("route.saved");
  });
  const nearbyCheck = () => run(async () => {
    const here = await currentPosition();
    if (!here) return t("route.noPosition");
    setNearby(await apiRequest<Nearby>(`/api/v1/routes/nearby-suppliers${q}&latitude=${here.latitude.toFixed(6)}&longitude=${here.longitude.toFixed(6)}&radius_meters=1500`));
    return undefined;
  });
  const recordMyPosition = (task: RouteTask) => run(async () => {
    const here = await currentPosition();
    if (!here) return t("route.noPosition");
    const result = await apiRequest<LocationResult>(`/api/v1/delivery-tasks/${task.id}/location${q}`, { method: "POST", body: JSON.stringify({ latitude: here.latitude.toFixed(6), longitude: here.longitude.toFixed(6), source: "gps", accuracy_meters: here.accuracy.toFixed(2), confirm: confirmLocation }) });
    onSaved?.();
    return t(`route.location.${result.reason}`, { customer: task.customer_name });
  });

  return (
    <div className="route-planner">
      <h5>{t("route.title")}</h5>
      <p className="muted">{t("route.body")}</p>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      <div className="category-actions">
        <button className="button" disabled={busy || tasks.length === 0} onClick={suggest} type="button">{t("route.suggest")}</button>
        <button className="text-button" disabled={busy} onClick={nearbyCheck} type="button">{t("route.nearby")}</button>
        <label className="field checkbox"><input checked={confirmLocation} type="checkbox" onChange={(event) => setConfirmLocation(event.target.checked)} /> <span>{t("route.confirmLocation")}</span></label>
      </div>
      {suggestion ? (
        <>
          <p className="muted"><strong>{suggestion.method === "openrouteservice" ? t("route.methodOnline") : t("route.methodOffline")}</strong>{suggestion.note ? ` · ${t("route.providerDown")}` : ""} · {t("route.notOptimal")}</p>
          <ol className="pickup-items route-order" aria-label={t("route.orderList")}>
            {order.map((stop, index) => (
              <li key={stop.task_id}>
                <strong>{index + 1}.</strong> {stop.customer_name}{!stop.has_location ? <small className="muted"> · {t("route.noLocation")}</small> : null}
                {" "}<button aria-label={t("route.up", { customer: stop.customer_name })} className="text-button" disabled={busy || index === 0} onClick={() => move(index, -1)} type="button">↑</button>
                {" "}<button aria-label={t("route.down", { customer: stop.customer_name })} className="text-button" disabled={busy || index === order.length - 1} onClick={() => move(index, 1)} type="button">↓</button>
              </li>
            ))}
          </ol>
          <button className="button" disabled={busy || order.length === 0} onClick={save} type="button">{t("route.save")}</button>
        </>
      ) : null}
      {tasks.length > 0 ? (
        <ul className="chips route-locations" aria-label={t("route.locationsTitle")}>
          {tasks.map((task) => <li key={task.id}><button className="text-button" disabled={busy} onClick={() => recordMyPosition(task)} type="button">{t("route.recordMyPosition", { customer: task.customer_name })}</button></li>)}
        </ul>
      ) : null}
      {nearby ? (
        <div className="nearby" aria-live="polite">
          <h6>{t("route.nearbyTitle", { radius: nearby.radius_meters })}</h6>
          {nearby.suppliers.length === 0 ? <p className="muted">{t("route.nearbyNone")}</p> : null}
          <ul className="pickup-items">
            {nearby.suppliers.map((supplier) => (
              <li key={supplier.supplier_id}>
                <strong>{supplier.supplier_name}</strong> · {supplier.distance_meters} m{supplier.address ? ` · ${supplier.address}` : ""}{supplier.contact_phone ? <> · <a dir="ltr" href={`tel:${supplier.contact_phone}`}>{supplier.contact_phone}</a></> : null}
                <div className="muted">{supplier.items.map((item) => `${item.remaining_quantity} × ${item.product_name} (${item.list_title})`).join(", ")}</div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
