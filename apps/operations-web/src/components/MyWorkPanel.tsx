import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useInRouterContext, useLocation } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis } from "../api/types";
import { browserOffline } from "../offline/network";
import { SYNC_COMPLETED_EVENT } from "../offline/events";
import { listOutbox } from "../offline/outbox";
import { syncNow } from "../offline/pull";
import { bootstrapLocalProjection, localSyncStatus } from "../offline/sync";
import { type CollectionClaim, queueDeliveryCompletion } from "../offline/supplierCommands";
import { useStopDirections } from "./directions";
import { DirectionsView } from "./DirectionsView";
import { Arrow, Icon } from "./Icon";
import { RoutePlanner } from "./RoutePlanner";
import { type MapRoute, StopMap } from "./StopMap";
import { ConfirmAction, ErrorState } from "./Ui";
import { SYNC_ANCHOR, WORK_ANCHOR } from "./workspaceSections";

/**
 * "My Work" (PHASE_07.md C/D/I): the assigned open deliveries of the signed-in member — a driver,
 * or the owner acting as operator. Contact, address, map link, items and the amount to collect;
 * never a cost, margin or someone else's task. Completion works offline: the command is queued
 * with the version this screen saw and applied exactly once on reconnect. The list itself is
 * cached in this browser's storage so the day's stops survive a lost connection.
 *
 * Presentation follows the Daylight work screen: an ordered stop list beside the selected stop
 * on wide screens, one focused pane on phones, and the completion action attached to the stop.
 * D-092: a map of the stops in route order; after a delivery the next stop opens by itself, the
 * rest can be re-planned from the delivered customer's saved location on request (no position is
 * read or tracked), and Navigate hands the directions to Google Maps. D-093: Directions shows the
 * road route from the member's position (read once on request) to the stop inside the app.
 */
interface Line { product_name: string; quantity: string; price_basis: ProductPriceBasis; pieces_per_box: number | null }
interface WorkTask { id: string; status: string; official_invoice_number: string | null; customer_name: string; customer_phone: string; customer_address: string | null; customer_latitude: string | null; customer_longitude: string | null; delivery_date: string | null; route_sequence: number | null; currency: string; amount_to_collect: string; items: Line[]; notes: string | null; version: number }
interface MyWork { tasks: WorkTask[]; membership_id: string; role: string }
interface Delivered { name: string; latitude: string | null; longitude: string | null }
interface Suggestion { method: string; stops: { task_id: string }[] }

const cacheKey = (tenantId: string, membershipId: string) => `tawzeevo.mywork.${tenantId}.${membershipId}`;

function unitLabel(t: (key: string) => string, line: Line): string {
  return line.price_basis === "BOX" ? t("tenantWorkspace.box") : t("tenantWorkspace.piece");
}

/** Reacts to the route hash (the phone navigation's anchors); only rendered inside a Router. */
function HashTarget({ onHash }: { onHash: (hash: string) => void }) {
  const location = useLocation();
  useEffect(() => { onHash(location.hash); }, [location.key, location.hash, onHash]);
  return null;
}

/** One pane (phones and tablets, below the 1100px list/detail layout): an open stop replaces the list. */
const ONE_PANE = "(max-width: 1099px)";
const singlePane = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(ONE_PANE).matches;

function useSinglePane(): boolean {
  const [single, setSingle] = useState(singlePane);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(ONE_PANE);
    const update = () => setSingle(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return single;
}

/** `ownerBrief` is the owner-only "today's priorities" band (D-089); a driver never receives it. */
export function MyWorkPanel({ tenantId, membershipId, ownerBrief }: { tenantId: string; membershipId: string; ownerBrief?: ReactNode }) {
  const { t, i18n } = useTranslation();
  const [work, setWork] = useState<MyWork>();
  const [fromCache, setFromCache] = useState(false);
  const [queued, setQueued] = useState<string[]>([]);
  const [doneIds, setDoneIds] = useState<string[]>([]);
  const [note, setNote] = useState("");
  // What was collected at this stop (D-114), asked before completing when money is owed.
  const [collection, setCollection] = useState<{ kind: "" | CollectionClaim["kind"]; amount: string }>({ kind: "", amount: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const [revokedReason, setRevokedReason] = useState<string>();
  const [selectedId, setSelectedId] = useState<string>();
  const [detailOpen, setDetailOpen] = useState(false);
  // The stop just delivered: the start for an on-request re-plan of the remaining stops.
  const [delivered, setDelivered] = useState<Delivered>();
  const directions = useStopDirections(tenantId);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const detailFeedback = useRef<HTMLDivElement>(null);
  const stopButtons = useRef(new Map<string, HTMLButtonElement>());
  const onePane = useSinglePane();
  const inRouter = useInRouterContext();
  const onHash = useCallback((hash: string) => {
    // A navigation to the work screen without an anchor (the owner's Work entry) returns to the list too.
    if (!hash) { setDetailOpen(false); return; }
    if (hash !== `#${WORK_ANCHOR}` && hash !== `#${SYNC_ANCHOR}`) return;
    setDetailOpen(false);
    requestAnimationFrame(() => {
      const target = document.getElementById(hash.slice(1));
      if (!target) return;
      if (typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "start" });
      target.focus({ preventScroll: true });
    });
  }, []);

  // Register this device for offline completions while online (a driver bootstrap downloads
  // nothing; an owner device that already bootstrapped from the Offline tab is left alone).
  const ensureDevice = useCallback(async () => {
    try {
      const status = await localSyncStatus(tenantId, membershipId);
      if (!status.bootstrapped_at) await bootstrapLocalProjection(tenantId, membershipId);
    } catch { /* offline or storage unavailable: completion still queues; sync retries registration */ }
  }, [tenantId, membershipId]);

  const load = useCallback(async (): Promise<MyWork> => {
    try {
      const fresh = await apiRequest<MyWork>(`/api/v1/delivery-tasks/my-work?tenant_id=${tenantId}`);
      setWork(fresh); setFromCache(false);
      try { localStorage.setItem(cacheKey(tenantId, membershipId), JSON.stringify(fresh)); } catch { /* storage may be unavailable */ }
      if (fresh.role === "driver") void ensureDevice();
      return fresh;
    } catch (problem) {
      // Offline: show the last downloaded list so the stops are still readable.
      if (!(problem instanceof TypeError) || !browserOffline()) throw problem;
      const cached = localStorage.getItem(cacheKey(tenantId, membershipId));
      if (!cached) throw problem;
      const stored = JSON.parse(cached) as MyWork;
      setWork(stored); setFromCache(true);
      return stored;
    }
  }, [tenantId, membershipId, ensureDevice]);
  useEffect(() => { load().catch(setError); }, [load]);
  // Completions queued on this device before a reload are still waiting in its outbox: list them
  // again, so each stop shows as queued and "Sync now" can send them (nothing else changes). After an
  // automatic send (D-098) the list is read again, so sent completions leave it and the stops refresh.
  useEffect(() => {
    let live = true;
    const waitingCompletions = () => listOutbox(tenantId, membershipId)
      .then((rows) => rows
        .filter((row) => row.entity_type === "delivery_task" && row.operation_type === "complete" && (row.state === "pending" || row.state === "sending" || row.state === "retryable_failed"))
        .map((row) => row.entity_id))
      .catch(() => [] as string[]); // no device storage: nothing was queued here
    void waitingCompletions().then((waiting) => {
      if (live && waiting.length) setQueued((current) => [...current, ...waiting.filter((id) => !current.includes(id))]);
    });
    const afterSync = () => {
      void waitingCompletions().then((waiting) => {
        if (!live) return;
        setQueued((current) => {
          const sent = current.filter((id) => !waiting.includes(id));
          if (sent.length) setDoneIds((done) => [...done, ...sent.filter((id) => !done.includes(id))]);
          return current.filter((id) => waiting.includes(id));
        });
        load().catch(() => undefined);
      });
    };
    window.addEventListener(SYNC_COMPLETED_EVENT, afterSync);
    return () => { live = false; window.removeEventListener(SYNC_COMPLETED_EVENT, afterSync); };
  }, [tenantId, membershipId, load]);

  const owes = (task: WorkTask) => Number(task.amount_to_collect) > 0;
  const claimFor = (task: WorkTask): CollectionClaim | null => {
    if (!owes(task) || !collection.kind) return null;
    return collection.kind === "PARTIAL" ? { kind: "PARTIAL", amount: collection.amount.trim() } : { kind: collection.kind };
  };
  // Answering is optional (no answer: no report, as before); a partial payment needs its amount.
  const claimReady = (task: WorkTask) => !owes(task) || collection.kind !== "PARTIAL"
    || (collection.kind === "PARTIAL" && Number(collection.amount) > 0 && Number(collection.amount) <= Number(task.amount_to_collect));
  const complete = (task: WorkTask) => {
    setBusy(true); setError(undefined); setNotice(undefined); setRevokedReason(undefined);
    const claim = claimFor(task);
    apiRequest<WorkTask>(`/api/v1/delivery-tasks/${task.id}/complete?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ expected_version: task.version, note: note || null, ...(claim ? { collection: claim } : {}) }) })
      .then(async () => {
        setCollection({ kind: "", amount: "" });
        setNote(""); setDoneIds((current) => [...current, task.id]); setDetailOpen(false);
        setDelivered({ name: task.customer_name, latitude: task.customer_latitude, longitude: task.customer_longitude });
        // The next stop in the saved order opens by itself (on a phone it replaces the list).
        const next = (await load()).tasks[0];
        if (next) openStop(next);
        setNotice(next ? `${t("myWork.completed")} ${t("myWork.nextStop", { customer: next.customer_name })}` : t("myWork.completed"));
      })
      .catch(async (problem: unknown) => {
        if (!(problem instanceof TypeError) || !browserOffline()) { setError(problem); return; }
        await (claim ? queueDeliveryCompletion(tenantId, membershipId, task.id, task.version, note || null, claim) : queueDeliveryCompletion(tenantId, membershipId, task.id, task.version, note || null));
        setCollection({ kind: "", amount: "" });
        setQueued((current) => [...current, task.id]);
        setNotice(t("myWork.queued"));
        setNote("");
      })
      .finally(() => setBusy(false));
  };
  // On request only: order the remaining stops from the delivered customer's saved location and
  // save that order, then open the new first stop. The member can still reorder by hand.
  const replan = () => {
    if (!delivered?.latitude || !delivered.longitude) return;
    const from = delivered;
    const remaining = (work?.tasks ?? []).map((task) => task.id);
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest<Suggestion>(`/api/v1/routes/suggest-order?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ origin: { latitude: from.latitude, longitude: from.longitude }, task_ids: remaining }) })
      .then((suggestion) => apiRequest(`/api/v1/routes/order?tenant_id=${tenantId}`, { method: "PUT", body: JSON.stringify({ task_ids: suggestion.stops.map((stop) => stop.task_id) }) }))
      .then(() => load())
      .then((fresh) => {
        setDelivered(undefined);
        const next = fresh.tasks[0];
        if (next) openStop(next);
        setNotice(t("myWork.replanned", { customer: from.name }));
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const sync = () => {
    setBusy(true); setError(undefined); setRevokedReason(undefined);
    ensureDevice().then(() => syncNow(tenantId, membershipId)).then((outcome) => {
      // Still offline: nothing was sent, so the queued completions stay listed and the member is told so.
      if (outcome.kind === "offline") { setNotice(t("sync.stillOffline")); return load(); }
      // This device lost access: its local outbox was set aside, so nothing waits here any more.
      if (outcome.kind === "revoked") { setQueued([]); setNotice(undefined); setRevokedReason(outcome.reason); return load(); }
      // Only a sync the server accepted in full fills the day meter: a completion refused as a
      // conflict, rejected or failed is not a delivery, so the result is reported instead of counted.
      // The queued list itself is handled as before.
      const refused = outcome.kind === "ok" && outcome.push.conflicts + outcome.push.rejected + outcome.push.failed > 0;
      if (outcome.kind === "ok" && !refused) setDoneIds((current) => [...current, ...queued]);
      setQueued([]);
      setNotice(outcome.kind === "ok" && refused
        ? t("sync.synced", { changes: t("sync.syncedChanges", { count: outcome.push.acknowledged }), received: outcome.pull.applied, conflicts: t("sync.syncedConflicts", { count: outcome.push.conflicts }) })
        : t("myWork.synced"));
      return load();
    }).catch(setError).finally(() => setBusy(false));
  };

  const tasks = useMemo(() => work?.tasks ?? [], [work]);
  const selected = tasks.find((task) => task.id === selectedId) ?? tasks[0];
  const selectedIndex = selected ? tasks.indexOf(selected) : -1;
  const doneCount = doneIds.length;
  const total = tasks.length + doneCount;
  const today = new Date();
  const dateParts = new Intl.DateTimeFormat(i18n.language === "ar" ? "ar-LB" : "en-GB", { day: "numeric", month: "short", weekday: "short" }).formatToParts(today);
  const part = (type: string) => dateParts.find((item) => item.type === type)?.value ?? "";
  const stopNumber = (task: WorkTask, index: number) => String(task.route_sequence ?? index + 1).padStart(2, "0");
  const mapRoutes = useMemo<MapRoute[]>(() => [{ key: "mine", stops: tasks.map((task, index) => ({ taskId: task.id, number: task.route_sequence ?? index + 1, name: task.customer_name, latitude: task.customer_latitude, longitude: task.customer_longitude })) }], [tasks]);

  // On a phone the selected stop replaces the list: move focus to its name and show the record
  // from its top (the way back, the stop number, the name), and bring focus back to the same stop
  // when returning, so the list position is preserved.
  const openStop = (task: WorkTask) => {
    if (task.id !== selectedId) setCollection({ kind: "", amount: "" });
    setSelectedId(task.id);
    setDetailOpen(true);
    setError(undefined);
    setNotice(undefined); // an earlier stop's result never appears inside the next stop
    setRevokedReason(undefined);
    if (singlePane()) requestAnimationFrame(() => {
      detailHeading.current?.focus({ preventScroll: true });
      const record = detailHeading.current?.closest("article");
      if (record && typeof record.scrollIntoView === "function") record.scrollIntoView({ block: "start" });
    });
  };
  const closeStop = () => {
    setDetailOpen(false);
    const id = selected?.id;
    requestAnimationFrame(() => { if (id) stopButtons.current.get(id)?.focus({ preventScroll: true }); });
  };

  // Results of the stop's actions (a failed or queued completion) appear where the member is: inside
  // the open stop on one pane, where the list is hidden; otherwise at the top of the list. Exactly one
  // copy is rendered, so the alert/status is announced once.
  const feedbackInDetail = detailOpen && onePane;
  const replanOffer = delivered && tasks.length > 1 && !fromCache ? (
    delivered.latitude && delivered.longitude
      ? <button className="text-button replan" disabled={busy} onClick={replan} type="button"><Icon name="sync" small />{t("myWork.replanFrom", { customer: delivered.name })}</button>
      : <p className="muted">{t("myWork.replanNoLocation", { customer: delivered.name })}</p>
  ) : null;
  const feedback = error || notice || revokedReason || replanOffer ? <>
    {error ? <ErrorState error={error} /> : null}
    {revokedReason ? <div className="notice notice-error" role="alert">{t("sync.revoked", { reason: revokedReason })}</div> : null}
    {notice ? <p className="form-status" role="status">{notice}</p> : null}
    {replanOffer}
  </> : null;
  useEffect(() => {
    if (!feedbackInDetail || (!error && !notice && !revokedReason)) return;
    const node = detailFeedback.current;
    if (node && typeof node.scrollIntoView === "function") node.scrollIntoView({ block: "nearest" });
  }, [feedbackInDetail, error, notice, revokedReason]);

  return (
    <section aria-labelledby="my-work-title" className={`my-work workspace${detailOpen ? " show-detail" : ""}`} id={WORK_ANCHOR} tabIndex={-1}>
      {inRouter ? <HashTarget onHash={onHash} /> : null}
      <div className="workspace-list">
        <header className="section-head">
          <p className="eyebrow">{t("myWork.kicker")}</p>
          <h3 id="my-work-title">{t("myWork.title")}</h3>
          <p>{t("myWork.body")}</p>
        </header>
        {feedbackInDetail ? null : feedback}
        {fromCache ? <p className="notice" role="status">{t("myWork.cached")}</p> : null}
        {queued.length ? <div className="banner" role="status"><Icon name="sync" /><span>{t("myWork.pending", { count: queued.length })}</span><a className="text-btn" href={`#${SYNC_ANCHOR}`}>{t("nav.sync")}</a></div> : null}

        <section className="day-summary" aria-label={t("myWork.workday")}>
          <span className="date-tab" aria-hidden="true">{part("month")}<strong>{part("day")}</strong>{part("weekday")}</span>
          <div className="day-summary-head">
            <p className="eyebrow">{t("myWork.workday")}</p>
            <h2>{tasks.length === 0 && doneCount > 0 ? t("myWork.summaryDone") : t("myWork.summaryTitle")}</h2>
            <p>{t("myWork.summaryBody")}</p>
          </div>
          {total > 0 ? <div className="day-meter" aria-hidden="true">{Array.from({ length: total }, (_, index) => <span className={index < doneCount ? "done" : ""} key={index} />)}</div> : null}
          <footer><span>{t("myWork.completedCount", { done: doneCount, total })}</span><span>{t("myWork.toVisit", { count: tasks.length })}</span></footer>
        </section>

        {ownerBrief}

        <label className="field field-wide"><span>{t("myWork.note")}</span><input maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></label>

        {work && tasks.length === 0 ? <p className="muted empty-copy">{t("myWork.empty")}</p> : null}
        {tasks.length > 0 ? (
          <>
            <div className="section-title"><h2>{t("myWork.stops")}</h2><small>{t("myWork.inRouteOrder")}</small></div>
            {!fromCache ? <StopMap onSelect={(id) => { const task = tasks.find((row) => row.id === id); if (task) openStop(task); }} routes={mapRoutes} selectedId={selected?.id} tenantId={tenantId} /> : null}
            <ol aria-label={t("myWork.title")} className="stop-list my-work-list">
              {tasks.map((task, index) => (
                <li className="stop-item" key={task.id}>
                  <button aria-current={selected?.id === task.id ? "true" : undefined} className={`stop-button${selected?.id === task.id ? " selected" : ""}`} onClick={() => openStop(task)} ref={(node) => { if (node) stopButtons.current.set(task.id, node); else stopButtons.current.delete(task.id); }} type="button">
                    <span className="stop-number">{stopNumber(task, index)}</span>
                    <span className="stop-copy"><strong>{task.customer_name}</strong><small>{task.customer_address ?? <bdi dir="ltr">{task.customer_phone}</bdi>}</small></span>
                    <span className="stop-amount"><bdi className="money" dir="ltr">{task.amount_to_collect} {task.currency}</bdi><small>{queued.includes(task.id) ? t("myWork.queuedShort") : t("myWork.toVisitLabel")}</small></span>
                    <Arrow />
                  </button>
                </li>
              ))}
            </ol>
          </>
        ) : null}

        {tasks.length > 0 && !fromCache ? <RoutePlanner onSaved={() => { load().catch(setError); }} tasks={tasks.map((task) => ({ id: task.id, customer_name: task.customer_name, version: task.version }))} tenantId={tenantId} /> : null}
        <section aria-labelledby="my-work-sync-title" className="work-sync" id={SYNC_ANCHOR} tabIndex={-1}>
          <h3 id="my-work-sync-title">{t("myWork.syncTitle")}</h3>
          <p className="muted">{t("myWork.syncBody")}</p>
          <p className="work-sync-count"><Icon name="sync" small />{queued.length ? t("myWork.pending", { count: queued.length }) : t("myWork.nothingQueued")}</p>
          {queued.length ? (
            <ul className="ledger" aria-label={t("myWork.pending", { count: queued.length })}>
              {queued.map((id) => <li key={id}><span className="ledger-copy"><strong>{tasks.find((task) => task.id === id)?.customer_name ?? id}</strong></span><span className="badge warn">{t("myWork.queuedShort")}</span></li>)}
            </ul>
          ) : null}
          <button className="button" disabled={busy || queued.length === 0} onClick={sync} type="button"><Icon name="sync" small />{t("sync.syncNow")}</button>
        </section>
        <p className="work-footnote"><Icon name="shield" small />{t("myWork.completionNote")}</p>
      </div>

      {selected ? (
        <article className="detail stop-detail">
            <div className="detail-inner has-action">
              <button className="text-btn mobile-back" onClick={closeStop} type="button"><Arrow back />{t("myWork.allStops")}</button>
              {feedbackInDetail && feedback ? <div className="detail-feedback" ref={detailFeedback}>{feedback}</div> : null}
              <div className="detail-top">
                <span className="eyebrow">{t("myWork.stop", { number: stopNumber(selected, selectedIndex) })}</span>
                <span className={`badge${queued.includes(selected.id) ? " warn" : ""}`}>{queued.includes(selected.id) ? t("myWork.queuedShort") : t("myWork.toVisitLabel")}</span>
              </div>
              <h2 className="detail-name" ref={detailHeading} tabIndex={-1}>{selected.customer_name}</h2>
              {selected.customer_address ? <p className="address"><Icon name="pin" small />{selected.customer_address}</p> : null}
              <div className="detail-contact">
                {selected.customer_latitude && selected.customer_longitude ? <>
                  {!fromCache ? <button className="button directions-button" disabled={directions.busy} onClick={() => directions.show(selected)} type="button"><Icon name="pin" small />{t("directions.button")}</button> : null}
                  <a className="button button-secondary navigate" href={`https://www.google.com/maps/dir/?api=1&destination=${selected.customer_latitude},${selected.customer_longitude}&travelmode=driving`} rel="noreferrer" target="_blank"><Icon name="van" small />{t("myWork.navigate")}</a>
                </> : null}
                <a className="button button-secondary" dir="ltr" href={`tel:${selected.customer_phone}`}><Icon name="phone" small /><span dir="ltr">{selected.customer_phone}</span></a>
                {selected.customer_latitude && selected.customer_longitude ? <a className="button button-secondary" href={`https://www.google.com/maps?q=${selected.customer_latitude},${selected.customer_longitude}`} rel="noreferrer" target="_blank"><Icon name="pin" small />{t("pickup.openMap")}</a> : null}
              </div>
              {directions.problem && directions.result === undefined ? <ErrorState error={directions.problem} /> : null}
              {directions.result?.taskId === selected.id ? <DirectionsView onClose={directions.clear} result={directions.result} /> : null}
              <div className="row"><h3>{t("myWork.forDelivery")}</h3>{selected.official_invoice_number ? <small className="muted"><bdi dir="ltr">{selected.official_invoice_number}</bdi></small> : null}</div>
              <ul className="line-list">
                {selected.items.map((line, index) => (
                  <li key={`${line.product_name}-${index}`}>
                    <span className="line-copy"><strong>{line.product_name}</strong>{line.pieces_per_box ? <small>{line.pieces_per_box} × {t("tenantWorkspace.piece")}</small> : null}</span>
                    <span className="line-quantity"><bdi dir="ltr">{line.quantity}</bdi> <small>{unitLabel(t, line)}</small></span>
                  </li>
                ))}
              </ul>
              {selected.delivery_date ? <p className="note"><Icon name="clock" small />{t("orders.deliveryDate")}: <bdi dir="ltr">{selected.delivery_date}</bdi></p> : null}
              {selected.notes ? <p className="note"><Icon name="info" small />{selected.notes}</p> : null}
            </div>
            <div className="action-area attached">
              <span className="context">
                <span className="detail-label">{t("myWork.collect")}</span>
                <strong className="amount"><bdi className="money" dir="ltr">{selected.amount_to_collect} {selected.currency}</bdi></strong>
              </span>
              {owes(selected) && !queued.includes(selected.id) ? (
                <fieldset className="collection-claim">
                  <legend>{t("collection.question")}</legend>
                  {(["FULL", "PARTIAL", "NONE"] as const).map((kind) => (
                    <label className="checkbox-row" key={kind}><input checked={collection.kind === kind} name={`collection-${selected.id}`} onChange={() => setCollection({ kind, amount: kind === "PARTIAL" ? collection.amount : "" })} type="radio" /><span>{t(`collection.kinds.${kind}`)}</span></label>
                  ))}
                  {collection.kind === "PARTIAL" ? <label className="field"><span>{t("collection.amountPaid", { currency: selected.currency })}</span><input dir="ltr" inputMode="decimal" max={selected.amount_to_collect} min="0.0001" required step="0.0001" type="number" value={collection.amount} onChange={(event) => setCollection({ kind: "PARTIAL", amount: event.target.value })} /></label> : null}
                  <small className="muted">{t("collection.notPaymentYet")}</small>
                </fieldset>
              ) : null}
              {queued.includes(selected.id)
                ? <button className="button" disabled type="button"><Icon name="check" small />{t("myWork.queuedShort")}</button>
                : <ConfirmAction confirmLabel={t("myWork.confirmDelivered")} disabled={busy || !claimReady(selected)} icon={<Icon name="check" small />} key={selected.id} label={t("delivery.complete")} onConfirm={() => complete(selected)}>{t("myWork.confirmDeliveredNote", { amount: `${selected.amount_to_collect} ${selected.currency}` })}</ConfirmAction>}
            </div>
            <p className="detail-bottom-note">{t("myWork.completionNote")}</p>
        </article>
      ) : null}
    </section>
  );
}
