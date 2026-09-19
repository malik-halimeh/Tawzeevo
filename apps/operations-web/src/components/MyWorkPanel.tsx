import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis } from "../api/types";
import { browserOffline } from "../offline/network";
import { syncNow } from "../offline/pull";
import { bootstrapLocalProjection } from "../offline/sync";
import { queueDeliveryCompletion } from "../offline/supplierCommands";
import { RoutePlanner } from "./RoutePlanner";
import { ErrorState } from "./Ui";

/**
 * "My Work" (PHASE_07.md C/D/I): the assigned open deliveries of the signed-in member — a driver,
 * or the owner acting as operator. Contact, address, map link, items and the amount to collect;
 * never a cost, margin or someone else's task. Completion works offline: the command is queued
 * with the version this screen saw and applied exactly once on reconnect. The list itself is
 * cached in this browser's storage so the day's stops survive a lost connection.
 */
interface Line { product_name: string; quantity: string; price_basis: ProductPriceBasis; pieces_per_box: number | null }
interface WorkTask { id: string; status: string; official_invoice_number: string | null; customer_name: string; customer_phone: string; customer_address: string | null; customer_latitude: string | null; customer_longitude: string | null; delivery_date: string | null; route_sequence: number | null; currency: string; amount_to_collect: string; items: Line[]; notes: string | null; version: number }
interface MyWork { tasks: WorkTask[]; membership_id: string; role: string }

const cacheKey = (tenantId: string, membershipId: string) => `tawzeevo.mywork.${tenantId}.${membershipId}`;

export function MyWorkPanel({ tenantId, membershipId }: { tenantId: string; membershipId: string }) {
  const { t } = useTranslation();
  const [work, setWork] = useState<MyWork>();
  const [fromCache, setFromCache] = useState(false);
  const [queued, setQueued] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const load = useCallback(async () => {
    try {
      const fresh = await apiRequest<MyWork>(`/api/v1/delivery-tasks/my-work?tenant_id=${tenantId}`);
      setWork(fresh); setFromCache(false);
      try { localStorage.setItem(cacheKey(tenantId, membershipId), JSON.stringify(fresh)); } catch { /* storage may be unavailable */ }
    } catch (problem) {
      // Offline: show the last downloaded list so the stops are still readable.
      if (!(problem instanceof TypeError) || !browserOffline()) throw problem;
      const cached = localStorage.getItem(cacheKey(tenantId, membershipId));
      if (cached) { setWork(JSON.parse(cached) as MyWork); setFromCache(true); } else throw problem;
    }
  }, [tenantId, membershipId]);
  useEffect(() => { load().catch(setError); }, [load]);

  const complete = (task: WorkTask) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest<WorkTask>(`/api/v1/delivery-tasks/${task.id}/complete?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ expected_version: task.version, note: note || null }) })
      .then(() => { setNotice(t("myWork.completed")); setNote(""); return load(); })
      .catch(async (problem: unknown) => {
        if (!(problem instanceof TypeError) || !browserOffline()) { setError(problem); return; }
        // Offline: make sure this device is registered (a driver bootstrap downloads nothing), then queue.
        try { await bootstrapLocalProjection(tenantId, membershipId); } catch { /* already registered or offline: the outbox still queues */ }
        await queueDeliveryCompletion(tenantId, membershipId, task.id, task.version, note || null);
        setQueued((current) => [...current, task.id]);
        setNotice(t("myWork.queued"));
        setNote("");
      })
      .finally(() => setBusy(false));
  };
  const sync = () => {
    setBusy(true); setError(undefined);
    syncNow(tenantId, membershipId).then(() => { setQueued([]); setNotice(t("myWork.synced")); return load(); }).catch(setError).finally(() => setBusy(false));
  };

  return (
    <section className="my-work" aria-labelledby="my-work-title">
      <header>
        <p className="section-kicker">{t("myWork.kicker")}</p>
        <h3 id="my-work-title">{t("myWork.title")}</h3>
        <p>{t("myWork.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      {fromCache ? <p className="notice" role="status">{t("myWork.cached")}</p> : null}
      {queued.length ? <div className="category-actions"><span className="muted">{t("myWork.pending", { count: queued.length })}</span><button className="button" disabled={busy} onClick={sync} type="button">{t("sync.syncNow")}</button></div> : null}
      <label className="field field-wide"><span>{t("myWork.note")}</span><input maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></label>
      {work && work.tasks.length === 0 ? <p className="muted">{t("myWork.empty")}</p> : null}
      {work && work.tasks.length > 0 && !fromCache ? <RoutePlanner onSaved={() => { load().catch(setError); }} tasks={work.tasks.map((task) => ({ id: task.id, customer_name: task.customer_name, version: task.version }))} tenantId={tenantId} /> : null}
      <ol className="pickup-items my-work-list" aria-label={t("myWork.title")}>
        {work?.tasks.map((task) => (
          <li className="content-card my-work-stop" key={task.id}>
            <strong>{task.route_sequence ? `${task.route_sequence}. ` : ""}{task.customer_name}</strong>
            <div className="muted"><a dir="ltr" href={`tel:${task.customer_phone}`}>{task.customer_phone}</a>{task.customer_address ? ` · ${task.customer_address}` : ""}{task.customer_latitude && task.customer_longitude ? <> · <a href={`https://www.google.com/maps?q=${task.customer_latitude},${task.customer_longitude}`} rel="noreferrer" target="_blank">{t("pickup.openMap")}</a></> : null}</div>
            <div>{task.items.map((line) => `${line.quantity} × ${line.product_name}`).join(", ")}</div>
            <div><strong>{t("delivery.collect")}: <bdi dir="ltr">{task.amount_to_collect} {task.currency}</bdi></strong>{task.official_invoice_number ? <span className="muted"> · {task.official_invoice_number}</span> : null}{task.notes ? <span className="muted"> · {task.notes}</span> : null}</div>
            <button className="button" disabled={busy || queued.includes(task.id)} onClick={() => complete(task)} type="button">{queued.includes(task.id) ? t("myWork.queuedShort") : t("delivery.complete")}</button>
          </li>
        ))}
      </ol>
    </section>
  );
}
