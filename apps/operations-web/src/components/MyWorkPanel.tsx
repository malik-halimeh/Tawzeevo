import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useInRouterContext, useLocation } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis } from "../api/types";
import { browserOffline } from "../offline/network";
import { syncNow } from "../offline/pull";
import { bootstrapLocalProjection, localSyncStatus } from "../offline/sync";
import { queueDeliveryCompletion } from "../offline/supplierCommands";
import { Arrow, Icon } from "./Icon";
import { RoutePlanner } from "./RoutePlanner";
import { ErrorState } from "./Ui";
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
 */
interface Line { product_name: string; quantity: string; price_basis: ProductPriceBasis; pieces_per_box: number | null }
interface WorkTask { id: string; status: string; official_invoice_number: string | null; customer_name: string; customer_phone: string; customer_address: string | null; customer_latitude: string | null; customer_longitude: string | null; delivery_date: string | null; route_sequence: number | null; currency: string; amount_to_collect: string; items: Line[]; notes: string | null; version: number }
interface MyWork { tasks: WorkTask[]; membership_id: string; role: string }

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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const [revokedReason, setRevokedReason] = useState<string>();
  const [selectedId, setSelectedId] = useState<string>();
  const [detailOpen, setDetailOpen] = useState(false);
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

  const load = useCallback(async () => {
    try {
      const fresh = await apiRequest<MyWork>(`/api/v1/delivery-tasks/my-work?tenant_id=${tenantId}`);
      setWork(fresh); setFromCache(false);
      try { localStorage.setItem(cacheKey(tenantId, membershipId), JSON.stringify(fresh)); } catch { /* storage may be unavailable */ }
      if (fresh.role === "driver") void ensureDevice();
    } catch (problem) {
      // Offline: show the last downloaded list so the stops are still readable.
      if (!(problem instanceof TypeError) || !browserOffline()) throw problem;
      const cached = localStorage.getItem(cacheKey(tenantId, membershipId));
      if (cached) { setWork(JSON.parse(cached) as MyWork); setFromCache(true); } else throw problem;
    }
  }, [tenantId, membershipId, ensureDevice]);
  useEffect(() => { load().catch(setError); }, [load]);

  const complete = (task: WorkTask) => {
    setBusy(true); setError(undefined); setNotice(undefined); setRevokedReason(undefined);
    apiRequest<WorkTask>(`/api/v1/delivery-tasks/${task.id}/complete?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ expected_version: task.version, note: note || null }) })
      .then(() => { setNotice(t("myWork.completed")); setNote(""); setDoneIds((current) => [...current, task.id]); setDetailOpen(false); return load(); })
      .catch(async (problem: unknown) => {
        if (!(problem instanceof TypeError) || !browserOffline()) { setError(problem); return; }
        await queueDeliveryCompletion(tenantId, membershipId, task.id, task.version, note || null);
        setQueued((current) => [...current, task.id]);
        setNotice(t("myWork.queued"));
        setNote("");
      })
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

  const tasks = work?.tasks ?? [];
  const selected = tasks.find((task) => task.id === selectedId) ?? tasks[0];
  const selectedIndex = selected ? tasks.indexOf(selected) : -1;
  const doneCount = doneIds.length;
  const total = tasks.length + doneCount;
  const today = new Date();
  const dateParts = new Intl.DateTimeFormat(i18n.language === "ar" ? "ar-LB" : "en-GB", { day: "numeric", month: "short", weekday: "short" }).formatToParts(today);
  const part = (type: string) => dateParts.find((item) => item.type === type)?.value ?? "";
  const stopNumber = (task: WorkTask, index: number) => String(task.route_sequence ?? index + 1).padStart(2, "0");

  // On a phone the selected stop replaces the list: move focus to its name and show the record
  // from its top (the way back, the stop number, the name), and bring focus back to the same stop
  // when returning, so the list position is preserved.
  const openStop = (task: WorkTask) => {
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
  const feedback = error || notice || revokedReason ? <>
    {error ? <ErrorState error={error} /> : null}
    {revokedReason ? <div className="notice notice-error" role="alert">{t("sync.revoked", { reason: revokedReason })}</div> : null}
    {notice ? <p className="form-status" role="status">{notice}</p> : null}
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
                <a className="button button-secondary" dir="ltr" href={`tel:${selected.customer_phone}`}><Icon name="phone" small /><span dir="ltr">{selected.customer_phone}</span></a>
                {selected.customer_latitude && selected.customer_longitude ? <a className="button button-secondary" href={`https://www.google.com/maps?q=${selected.customer_latitude},${selected.customer_longitude}`} rel="noreferrer" target="_blank"><Icon name="pin" small />{t("pickup.openMap")}</a> : null}
              </div>
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
              <button className="button" disabled={busy || queued.includes(selected.id)} onClick={() => complete(selected)} type="button"><Icon name="check" small />{queued.includes(selected.id) ? t("myWork.queuedShort") : t("delivery.complete")}</button>
            </div>
            <p className="detail-bottom-note">{t("myWork.completionNote")}</p>
        </article>
      ) : null}
    </section>
  );
}
