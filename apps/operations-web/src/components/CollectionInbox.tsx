import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { COLLECTION_REPORTS_KEY, type CollectionReport, fetchPendingCollections } from "./collectionReportsApi";
import { ConfirmAction, ErrorState } from "./Ui";
import { sectionHref } from "./workspaceSections";

/**
 * Payments drivers reported at deliveries, waiting for the owner (D-114). Confirm records the
 * receipt through the existing receipt service, allocated to that invoice; "Not paid" is only
 * acknowledged; Reject needs a reason. Nothing here changes a balance before Confirm.
 */
export function CollectionInbox({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const reports = useQuery({ queryKey: [COLLECTION_REPORTS_KEY, tenantId], queryFn: () => fetchPendingCollections(tenantId) });
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const decide = (report: CollectionReport, action: "confirm" | "reject") => {
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest(`/api/v1/collection-reports/${report.id}/${action}?tenant_id=${tenantId}`, { method: "POST", ...(action === "reject" ? { body: JSON.stringify({ reason: reason.trim() }) } : {}) })
      .then(async () => {
        setNotice(t(action === "reject" ? "collection.rejected" : report.kind === "NONE" ? "collection.acknowledged" : "collection.confirmed"));
        setRejecting(null); setReason("");
        await Promise.all([COLLECTION_REPORTS_KEY, "collections-to-record"].map((key) => queryClient.invalidateQueries({ queryKey: [key, tenantId] })));
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const rows = reports.data ?? [];
  if (!rows.length && !notice && !error) return null;
  return (
    <section aria-labelledby="collection-inbox-title" className="collection-inbox">
      <h3 id="collection-inbox-title">{t("collection.inbox")}</h3>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      <ul aria-label={t("collection.inbox")} className="owner-today-list">
        {rows.map((report) => (
          <li key={report.id}>
            <span>
              <strong>{report.customer_name}</strong> · <Link to={sectionHref("invoices", tenantId, { invoice: report.invoice_id })}><bdi dir="ltr">{report.official_invoice_number ?? "…"}</bdi></Link>
              <small> · {t(`collection.kinds.${report.kind}`)}{report.reporter_name ? ` · ${report.reporter_name}` : ""}</small>
            </span>
            {report.amount ? <bdi className="money" dir="ltr">{report.amount} {report.currency}</bdi> : <span className="muted">—</span>}
            <span className="application-actions">
              <ConfirmAction confirmLabel={t(report.kind === "NONE" ? "collection.acknowledgeYes" : "collection.confirmYes")} disabled={busy} label={t(report.kind === "NONE" ? "collection.acknowledge" : "collection.confirm")} onConfirm={() => decide(report, "confirm")}>
                {report.kind === "NONE" ? t("collection.acknowledgeExplain") : t("collection.confirmExplain", { amount: `${report.amount ?? ""} ${report.currency}` })}
              </ConfirmAction>
              {rejecting === report.id ? (
                <>
                  <label className="field"><span>{t("pickupReport.reason")}</span><input maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                  <button className="button button-danger" disabled={busy || !reason.trim()} onClick={() => decide(report, "reject")} type="button">{t("pickupReport.reject")}</button>
                  <button className="text-button" onClick={() => setRejecting(null)} type="button">{t("common.cancel")}</button>
                </>
              ) : <button className="text-button danger-link" disabled={busy} onClick={() => { setRejecting(report.id); setReason(""); }} type="button">{t("pickupReport.reject")}</button>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
