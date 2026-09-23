import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { OutboxRecord } from "../offline/db";
import { acceptServerVersion, listOutbox, retryDeadLetters, retryWithServerVersion } from "../offline/outbox";
import { type SyncOutcome, syncNow } from "../offline/pull";
import { bootstrapLocalProjection, localSyncStatus, type BootstrapProgress, type LocalSyncStatus } from "../offline/sync";
import { ErrorState } from "./Ui";

/**
 * Owner-facing offline desk (PHASE_04.md M): device identity, download/sync state, local counts,
 * and the outbox with pending, conflict, rejected and dead-letter work that is never hidden.
 */
export function SyncPanel({ tenantId, membershipId }: { tenantId: string; membershipId: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<LocalSyncStatus>();
  const [outbox, setOutbox] = useState<OutboxRecord[]>([]);
  const [progress, setProgress] = useState<BootstrapProgress>();
  const [outcome, setOutcome] = useState<SyncOutcome>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);

  const refresh = useCallback(async () => {
    try {
      setStatus(await localSyncStatus(tenantId, membershipId));
      setOutbox(await listOutbox(tenantId, membershipId));
    } catch (caught) { setError(caught); }
  }, [tenantId, membershipId]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up); window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);

  const run = (action: () => Promise<void>) => {
    setBusy(true); setError(undefined);
    action().catch(setError).finally(() => { setBusy(false); void refresh(); });
  };

  const bootstrap = () => run(async () => { setProgress(undefined); setStatus(await bootstrapLocalProjection(tenantId, membershipId, setProgress)); });
  const sync = () => run(async () => { setOutcome(await syncNow(tenantId, membershipId)); });

  const stateLabel = (state: OutboxRecord["state"]) => t(`sync.state.${state}`);
  const problems = outbox.filter((row) => row.state !== "acknowledged");

  return (
    <section className="sync-panel" aria-labelledby="sync-panel-title">
      <header>
        <p className="section-kicker">{t("sync.kicker")}</p>
        <h3 id="sync-panel-title">{t("sync.title")}</h3>
        <p>{t("sync.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {outcome?.kind === "revoked" ? <div className="notice notice-error" role="alert">{t("sync.revoked", { reason: outcome.reason })}</div> : null}
      {outcome?.kind === "offline" ? <p className="form-status" role="status">{t("sync.stillOffline")}</p> : null}
      {outcome?.kind === "ok" ? <p className="form-status" role="status">{t("sync.synced", { changes: t("sync.syncedChanges", { count: outcome.push.acknowledged }), received: outcome.pull.applied, conflicts: t("sync.syncedConflicts", { count: outcome.push.conflicts }) })}</p> : null}
      <dl className="sync-facts">
        <div><dt>{t("sync.connection")}</dt><dd><span className={`status-badge ${online ? "status-current" : "status-closed"}`}>{t(online ? "sync.online" : "sync.offline")}</span></dd></div>
        <div><dt>{t("sync.device")}</dt><dd><code dir="ltr">{status?.device_installation_id ?? "—"}</code></dd></div>
        <div><dt>{t("sync.lastDownload")}</dt><dd>{status?.bootstrapped_at ? <time dateTime={status.bootstrapped_at}>{new Date(status.bootstrapped_at).toLocaleString()}</time> : t("sync.never")}</dd></div>
        <div><dt>{t("sync.cursor")}</dt><dd dir="ltr">{status?.cursor ?? 0}</dd></div>
        <div><dt>{t("sync.localCounts")}</dt><dd dir="ltr">{status ? `${status.counts.customers} / ${status.counts.products} / ${status.counts.invoices}` : "—"}</dd></div>
        <div><dt>{t("sync.pendingWork")}</dt><dd dir="ltr">{status?.counts.outbox_pending ?? 0}</dd></div>
      </dl>
      <div className="sync-actions">
        <button className="button" disabled={busy || !online} onClick={sync} type="button">{busy ? t("sync.syncing") : t("sync.syncNow")}</button>
        <button className="button secondary-button" disabled={busy || !online} onClick={bootstrap} type="button">{t(status?.bootstrapped_at ? "sync.downloadAgain" : "sync.download")}</button>
        {progress ? <span role="status">{t("sync.progress", { collection: progress.collection, count: progress.downloaded })}</span> : null}
      </div>

      <section className="outbox" aria-labelledby="outbox-title">
        <h4 id="outbox-title">{t("sync.outboxTitle")}</h4>
        {problems.length === 0 ? <p className="empty-note">{t("sync.outboxEmpty")}</p> : (
          <ul className="outbox-list">
            {problems.map((row) => (
              <li key={row.seq} className={`outbox-${row.state}`}>
                <div>
                  <span className={`status-badge outbox-state-${row.state}`}>{stateLabel(row.state)}</span>
                  <strong>{t(`sync.entity.${row.entity_type}`)} · {t(`sync.operation.${row.operation_type}`)}</strong>
                  <time dateTime={row.client_timestamp}>{new Date(row.client_timestamp).toLocaleString()}</time>
                  {row.last_error ? <small>{row.last_error}</small> : null}
                </div>
                {row.state === "conflict" ? (
                  <div className="outbox-actions">
                    <button className="text-button" disabled={busy} onClick={() => run(() => acceptServerVersion(tenantId, membershipId, row.seq!))} type="button">{t("sync.keepServer")}</button>
                    <button className="text-button" disabled={busy} onClick={() => run(() => retryWithServerVersion(tenantId, membershipId, row.seq!))} type="button">{t("sync.resendMine")}</button>
                  </div>
                ) : null}
                {row.state === "dead_letter" ? (
                  <div className="outbox-actions">
                    <button className="text-button" disabled={busy} onClick={() => run(async () => { await retryDeadLetters(tenantId, membershipId); })} type="button">{t("sync.retryDead")}</button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
      <p className="backend-note">{t("sync.note")}</p>
    </section>
  );
}
