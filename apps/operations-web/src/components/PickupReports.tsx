import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { readLastChoice } from "./lastChoice";
import { PICKUP_REPORTS_KEY, type PickupReport, fetchPendingPickups } from "./pickupReportsApi";
import { ConfirmAction, ErrorState } from "./Ui";

/**
 * Pickup reports (D-106). The runner reports what was picked up from one supplier for one list and
 * what was paid; nothing is purchased until the owner confirms, which records one purchase through
 * the existing purchase service. The owner can reject with a reason. Online only.
 */
interface ReportItem { item_id: string; product_name: string; remaining_quantity: string }

/** The runner's form for one supplier of one list: quantity picked up and unit cost paid per line. */
export function ReportPickupForm({ tenantId, listId, supplierId, items }: { tenantId: string; listId: string; supplierId: string; items: ReportItem[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [currency, setCurrency] = useState(() => readLastChoice("currency", tenantId) ?? "USD");
  const [values, setValues] = useState<Record<string, { quantity: string; unitCost: string }>>(() => Object.fromEntries(items.map((item) => [item.item_id, { quantity: String(Number(item.remaining_quantity)), unitCost: "" }])));
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [sent, setSent] = useState(false);
  // One key per report attempt, kept until the server accepts it: a retry never makes a second report.
  const key = useRef<string>(undefined);

  if (sent) return <p className="form-status" role="status">{t("pickupReport.sent")}</p>;
  if (!open) return <button className="button button-secondary" onClick={() => setOpen(true)} type="button">{t("pickupReport.report")}</button>;

  const lines = items
    .map((item) => ({ item, value: values[item.item_id] ?? { quantity: "", unitCost: "" } }))
    .filter(({ value }) => Number(value.quantity) > 0);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    key.current ??= crypto.randomUUID();
    setBusy(true); setError(undefined);
    apiRequest(`/api/v1/procurement/pickup-reports?tenant_id=${tenantId}`, {
      method: "POST",
      body: JSON.stringify({
        idempotency_key: key.current, list_id: listId, supplier_id: supplierId, currency, notes: notes.trim() || null,
        lines: lines.map(({ item, value }) => ({ procurement_item_id: item.item_id, quantity: value.quantity, unit_cost: value.unitCost })),
      }),
    })
      .then(() => { key.current = undefined; setSent(true); })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  return (
    <form aria-label={t("pickupReport.report")} className="form-stack pickup-report-form" onSubmit={submit}>
      <p className="muted">{t("pickupReport.explain")}</p>
      {items.map((item) => {
        const value = values[item.item_id] ?? { quantity: "", unitCost: "" };
        const set = (change: Partial<typeof value>) => setValues({ ...values, [item.item_id]: { ...value, ...change } });
        return (
          <fieldset className="inline-form" key={item.item_id}>
            <legend>{item.product_name}</legend>
            <label className="field"><span>{t("pickupReport.quantity")}</span><input dir="ltr" inputMode="decimal" min="0" step="0.0001" type="number" value={value.quantity} onChange={(event) => set({ quantity: event.target.value })} /></label>
            <label className="field"><span>{t("pickupReport.unitCost", { currency })}</span><input dir="ltr" inputMode="decimal" min="0" required={Number(value.quantity) > 0} step="0.0001" type="number" value={value.unitCost} onChange={(event) => set({ unitCost: event.target.value })} /></label>
          </fieldset>
        );
      })}
      <label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} minLength={3} required value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label>
      <label className="field"><span>{t("supplierSetup.notes")}</span><input maxLength={500} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      {error ? <ErrorState error={error} /> : null}
      <div className="form-actions">
        <button className="button" disabled={busy || lines.length === 0} type="submit">{busy ? t("common.sending") : t("pickupReport.send")}</button>
        <button className="text-button" onClick={() => setOpen(false)} type="button">{t("common.cancel")}</button>
      </div>
    </form>
  );
}

/** The owner's inbox of pickups to confirm, shown in Buying. */
export function PickupInbox({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const reports = useQuery({ queryKey: [PICKUP_REPORTS_KEY, tenantId], queryFn: () => fetchPendingPickups(tenantId) });
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const decide = (report: PickupReport, action: "confirm" | "reject") => {
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest(`/api/v1/procurement/pickup-reports/${report.id}/${action}?tenant_id=${tenantId}`, { method: "POST", ...(action === "reject" ? { body: JSON.stringify({ reason: reason.trim() }) } : {}) })
      .then(async () => {
        setNotice(t(action === "confirm" ? "pickupReport.confirmed" : "pickupReport.rejected"));
        setRejecting(null); setReason("");
        await queryClient.invalidateQueries({ queryKey: [PICKUP_REPORTS_KEY, tenantId] });
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const rows = reports.data ?? [];
  if (!rows.length && !notice && !error) return null;
  return (
    <article aria-labelledby="pickup-inbox-title" className="content-card pickup-inbox">
      <h4 id="pickup-inbox-title">{t("pickupReport.inbox")}</h4>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      <ul aria-label={t("pickupReport.inbox")} className="pickup-inbox-list">
        {rows.map((report) => (
          <li key={report.id}>
            <p><strong>{report.supplier_name}</strong> · {report.list_title} · {report.reporter_name}</p>
            <ul className="pickup-items">
              {report.lines.map((line) => <li key={line.procurement_item_id}><bdi dir="ltr">{Number(line.quantity)}</bdi> × {line.product_name} @ <bdi dir="ltr">{line.unit_cost} {report.currency}</bdi></li>)}
            </ul>
            <p>{t("pickupReport.total")}: <bdi dir="ltr">{report.total} {report.currency}</bdi>{report.notes ? <> · <span className="muted">{report.notes}</span></> : null}</p>
            <div className="form-actions">
              <ConfirmAction confirmLabel={t("pickupReport.confirmYes")} disabled={busy} label={t("pickupReport.confirm")} onConfirm={() => decide(report, "confirm")}>{t("pickupReport.confirmExplain")}</ConfirmAction>
              {rejecting === report.id ? (
                <>
                  <label className="field"><span>{t("pickupReport.reason")}</span><input maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                  <button className="button button-danger" disabled={busy || !reason.trim()} onClick={() => decide(report, "reject")} type="button">{t("pickupReport.reject")}</button>
                  <button className="text-button" onClick={() => setRejecting(null)} type="button">{t("common.cancel")}</button>
                </>
              ) : <button className="text-button danger-link" disabled={busy} onClick={() => { setRejecting(report.id); setReason(""); }} type="button">{t("pickupReport.reject")}</button>}
            </div>
          </li>
        ))}
      </ul>
    </article>
  );
}
