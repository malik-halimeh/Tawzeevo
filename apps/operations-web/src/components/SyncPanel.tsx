import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { bootstrapLocalProjection, localSyncStatus, type BootstrapProgress, type LocalSyncStatus } from "../offline/sync";
import { ErrorState } from "./Ui";

/**
 * Owner-facing offline status (PHASE_04.md M): device identity, last download, local counts and
 * the bootstrap action. Pending/conflict/rejected outbox views are added with the outbox milestone.
 */
export function SyncPanel({ tenantId, membershipId }: { tenantId: string; membershipId: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<LocalSyncStatus>();
  const [progress, setProgress] = useState<BootstrapProgress>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);

  const refresh = useCallback(async () => {
    try { setStatus(await localSyncStatus(tenantId, membershipId)); } catch (caught) { setError(caught); }
  }, [tenantId, membershipId]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up); window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);

  const bootstrap = () => {
    setBusy(true); setError(undefined); setProgress(undefined);
    bootstrapLocalProjection(tenantId, membershipId, setProgress)
      .then(setStatus)
      .catch(setError)
      .finally(() => setBusy(false));
  };

  return (
    <section className="sync-panel" aria-labelledby="sync-panel-title">
      <header>
        <p className="section-kicker">{t("sync.kicker")}</p>
        <h3 id="sync-panel-title">{t("sync.title")}</h3>
        <p>{t("sync.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      <dl className="sync-facts">
        <div><dt>{t("sync.connection")}</dt><dd><span className={`status-badge ${online ? "status-current" : "status-closed"}`}>{t(online ? "sync.online" : "sync.offline")}</span></dd></div>
        <div><dt>{t("sync.device")}</dt><dd><code dir="ltr">{status?.device_installation_id ?? "—"}</code></dd></div>
        <div><dt>{t("sync.lastDownload")}</dt><dd>{status?.bootstrapped_at ? <time dateTime={status.bootstrapped_at}>{new Date(status.bootstrapped_at).toLocaleString()}</time> : t("sync.never")}</dd></div>
        <div><dt>{t("sync.cursor")}</dt><dd dir="ltr">{status?.cursor ?? 0}</dd></div>
        <div><dt>{t("sync.localCounts")}</dt><dd dir="ltr">{status ? `${status.counts.customers} / ${status.counts.products} / ${status.counts.invoices}` : "—"}</dd></div>
        <div><dt>{t("sync.pendingWork")}</dt><dd dir="ltr">{status?.counts.outbox_pending ?? 0}</dd></div>
      </dl>
      <div className="sync-actions">
        <button className="button" disabled={busy || !online} onClick={bootstrap} type="button">{busy ? t("sync.downloading") : t("sync.download")}</button>
        {progress ? <span role="status">{t("sync.progress", { collection: progress.collection, count: progress.downloaded })}</span> : null}
      </div>
      <p className="backend-note">{t("sync.note")}</p>
    </section>
  );
}
