import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { type BackupConnection, PENDING_CONNECT_KEY } from "../backup/connect";
import { ErrorState } from "./Ui";

/**
 * Owner backup desk (PHASE_04.md L/M; D-055..D-057): connect one Google Drive folder with the
 * narrowest scope, run and verify encrypted backups, and read the retained history. The panel
 * never sees keys or tokens; the server only reports manifests and outcomes.
 */
export interface BackupRecord {
  id: string;
  kind: "DAILY" | "MONTHLY" | "MANUAL";
  status: "RUNNING" | "UPLOADED" | "FAILED" | "DELETED";
  file_name: string | null;
  byte_size: number | null;
  checksum: string | null;
  manifest: { counts?: Record<string, number>; migration_version?: string; encryption?: { algorithm?: string } };
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RestoreRecord {
  id: string;
  backup_id: string;
  mode: "VERIFY" | "IMPORT";
  status: "VERIFIED" | "IMPORTED" | "FAILED";
  report: { rows?: number; consistent?: boolean; error?: string; message?: string };
  created_at: string;
}

export interface BackupStatus {
  connection: BackupConnection | null;
  latest_backup: BackupRecord | null;
  latest_restore: RestoreRecord | null;
  backups: BackupRecord[];
  retention: { daily: number; monthly: number };
}

export function BackupPanel({ tenantId, initialNotice }: { tenantId: string; initialNotice?: string | undefined }) {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<BackupStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string | undefined>(initialNotice);

  const refresh = useCallback(async () => {
    try {
      setStatus(await apiRequest<BackupStatus>(`/api/v1/tenants/${tenantId}/backup?tenant_id=${tenantId}`));
    } catch (caught) {
      setError(caught);
    }
  }, [tenantId]);

  useEffect(() => { void refresh(); }, [refresh]);

  const run = (action: () => Promise<void>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    action().catch(setError).finally(() => { setBusy(false); void refresh(); });
  };

  const connect = () => run(async () => {
    const { authorization_url } = await apiRequest<{ authorization_url: string; scope: string }>(
      `/api/v1/tenants/${tenantId}/backup/google/authorize?tenant_id=${tenantId}`,
      { method: "POST" },
    );
    try { sessionStorage.setItem(PENDING_CONNECT_KEY, tenantId); } catch { /* private mode: the callback asks again */ }
    window.location.assign(authorization_url);
  });
  const disconnect = () => run(async () => {
    await apiRequest<void>(`/api/v1/tenants/${tenantId}/backup/google/disconnect?tenant_id=${tenantId}`, { method: "POST" });
    setNotice(t("backup.disconnected"));
  });
  const backupNow = () => run(async () => {
    const backup = await apiRequest<BackupRecord>(`/api/v1/tenants/${tenantId}/backup/run?tenant_id=${tenantId}`, { method: "POST" });
    setNotice(t("backup.uploaded", { name: backup.file_name ?? "" }));
  });
  const verify = (backupId: string) => run(async () => {
    const drill = await apiRequest<RestoreRecord>(`/api/v1/tenants/${tenantId}/backup/${backupId}/verify?tenant_id=${tenantId}`, { method: "POST" });
    setNotice(t("backup.verified", { rows: drill.report.rows ?? 0 }));
  });

  const when = (value: string | null) => (value ? new Date(value).toLocaleString(i18n.language === "ar" ? "ar-LB" : "en-GB") : t("backup.never"));
  const size = (bytes: number | null) => (bytes == null ? "" : `${(bytes / 1024).toFixed(1)} KB`);
  const rows = (backup: BackupRecord) => Object.values(backup.manifest.counts ?? {}).reduce((sum, count) => sum + count, 0);

  return (
    <section className="backup-panel" aria-labelledby="backup-panel-title">
      <header>
        <p className="section-kicker">{t("backup.kicker")}</p>
        <h3 id="backup-panel-title">{t("backup.title")}</h3>
        <p>{t("backup.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}

      <dl className="sync-facts">
        <div><dt>{t("backup.connection")}</dt><dd>{status?.connection ? t("backup.connectedAs", { email: status.connection.account_email, folder: status.connection.folder_name }) : t("backup.notConnected")}</dd></div>
        <div><dt>{t("backup.lastBackup")}</dt><dd>{status?.latest_backup ? `${when(status.latest_backup.completed_at)} · ${t(`backup.kind.${status.latest_backup.kind}`)} · ${rows(status.latest_backup)} ${t("backup.rows")}` : t("backup.never")}</dd></div>
        <div><dt>{t("backup.lastDrill")}</dt><dd>{status?.latest_restore ? `${when(status.latest_restore.created_at)} · ${t(`backup.restoreStatus.${status.latest_restore.status}`)}` : t("backup.never")}</dd></div>
        <div><dt>{t("backup.retention")}</dt><dd>{status ? t("backup.retentionValue", { daily: status.retention.daily, monthly: status.retention.monthly }) : ""}</dd></div>
      </dl>
      {status?.connection?.last_error ? <div className="notice notice-error" role="alert">{status.connection.last_error}</div> : null}

      <div className="category-actions">
        {status?.connection ? (
          <>
            <button className="button" disabled={busy} onClick={backupNow} type="button">{busy ? t("backup.working") : t("backup.backupNow")}</button>
            <button className="text-button" disabled={busy} onClick={disconnect} type="button">{t("backup.disconnect")}</button>
          </>
        ) : (
          <button className="button" disabled={busy || !status} onClick={connect} type="button">{t("backup.connect")}</button>
        )}
      </div>
      <p className="muted">{t("backup.scopeNote")}</p>

      <h4>{t("backup.historyTitle")}</h4>
      {status && status.backups.length === 0 ? <p>{t("backup.historyEmpty")}</p> : null}
      <ul className="outbox-list">
        {status?.backups.map((backup) => (
          <li className={`outbox-row outbox-${backup.status.toLowerCase()}`} key={backup.id}>
            <div>
              <strong>{t(`backup.kind.${backup.kind}`)}</strong> · {when(backup.created_at)}
              <span className="status-badge">{t(`backup.status.${backup.status}`)}</span>
              {backup.status === "UPLOADED" ? <small dir="ltr"> {size(backup.byte_size)} · {rows(backup)} {t("backup.rows")} · sha256 {backup.checksum?.slice(0, 12)}…</small> : null}
              {backup.error ? <small className="error-text"> {backup.error}</small> : null}
            </div>
            {backup.status === "UPLOADED" ? <button className="text-button" disabled={busy} onClick={() => verify(backup.id)} type="button">{t("backup.verify")}</button> : null}
          </li>
        ))}
      </ul>
      <p className="muted">{t("backup.restoreNote")}</p>
    </section>
  );
}
