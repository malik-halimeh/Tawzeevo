import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { SupplierBalanceRow } from "./supplierBalances";
import { ConfirmAction, ErrorState, Pagination } from "./Ui";

/**
 * Supplier balances for every supplier and the supplier payment history (D-100). Balances are the
 * server's per-currency sums of the supplier ledger (never added across currencies). Any listed
 * payment can be reversed through the existing reversal, which keeps its rules: a reversal is a
 * new compensating entry, a reversal cannot itself be reversed, and a payment is reversed once.
 */
interface HistoryRow {
  id: string; supplier_id: string; supplier_name: string; direction: "SUPPLIER_PAYMENT" | "SUPPLIER_PAYMENT_REVERSAL"; currency: string; amount: string;
  paid_at: string; recorded_at: string; method: string | null; reference: string | null; notes: string | null; prepayment: boolean;
  reverses_payment_id: string | null; reversed_by_payment_id: string | null;
}
interface HistoryPage { page: number; limit: number; total: number; total_pages: number; payments: HistoryRow[] }

const PAGE_SIZE = 20;

export function BalanceChips({ balances }: { balances: SupplierBalanceRow["balances"] | undefined }) {
  const { t } = useTranslation();
  if (!balances) return null;
  if (!balances.length) return <span className="muted"> · {t("supplierHistory.noBalance")}</span>;
  return (
    <span className="balance-chips" aria-label={t("supplierLedger.payable")}>
      {balances.map((row) => <span className="balance-chip" dir="ltr" key={row.currency}>{row.balance} {row.currency}</span>)}
    </span>
  );
}

export function SupplierPaymentHistory({ tenantId, suppliers, version, onChanged }: {
  tenantId: string; suppliers: { id: string; name: string }[]; version: number; onChanged: () => void;
}) {
  const { t, i18n } = useTranslation();
  const [supplierId, setSupplierId] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<HistoryPage>();
  const [reversing, setReversing] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const load = useCallback(async () => {
    const filter = supplierId ? `&supplier_id=${supplierId}` : "";
    setData(await apiRequest<HistoryPage>(`/api/v1/payments/supplier-payments?tenant_id=${tenantId}&page=${page}&limit=${PAGE_SIZE}${filter}`));
  }, [tenantId, supplierId, page]);

  useEffect(() => { load().catch(setError); }, [load, version]);

  const payments = data?.payments ?? [];
  const when = (value: string) => new Date(value).toLocaleDateString(i18n.language === "ar" ? "ar-LB" : "en-GB");

  const reverse = (row: HistoryRow) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest(`/api/v1/payments/supplier-payments/${row.id}/reverse?tenant_id=${tenantId}`, {
      method: "POST",
      body: JSON.stringify({ idempotency_key: crypto.randomUUID(), reason: reason.trim() }),
    })
      .then(() => {
        setReversing(null); setReason("");
        setNotice(t("supplierLedger.reversed"));
        onChanged();
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  return (
    <article className="panel supplier-history" aria-labelledby="supplier-history-title">
      <h4 id="supplier-history-title">{t("supplierHistory.title")}</h4>
      <p className="backend-note">{t("supplierHistory.body")}</p>
      <label className="field"><span>{t("supplierHistory.filter")}</span>
        <select value={supplierId} onChange={(event) => { setSupplierId(event.target.value); setPage(1); }}>
          <option value="">{t("supplierHistory.allSuppliers")}</option>
          {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
        </select>
      </label>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      {data && payments.length === 0 ? <p className="empty-note">{t("supplierHistory.empty")}</p> : null}
      {payments.length ? (
        <ul aria-label={t("supplierHistory.title")} className="supplier-history-list">
          {payments.map((row) => {
            const reversal = row.direction === "SUPPLIER_PAYMENT_REVERSAL";
            return (
              <li key={row.id}>
                <div className="supplier-row">
                  <div>
                    <strong>{row.supplier_name}</strong>
                    {" · "}<bdi dir="ltr">{reversal ? "−" : ""}{row.amount} {row.currency}</bdi>
                    {" · "}<time dateTime={row.paid_at}>{when(row.paid_at)}</time>
                    {row.method ? <span className="muted"> · {t(`invoiceEditor.methods.${row.method}`, { defaultValue: row.method })}</span> : null}
                    {row.reference ? <span className="muted"> · <bdi dir="ltr">{row.reference}</bdi></span> : null}
                    {row.prepayment ? <span className="status-badge">{t("supplierHistory.prepayment")}</span> : null}
                    {reversal ? <span className="status-badge">{t("supplierHistory.reversal")}</span> : null}
                    {row.reversed_by_payment_id ? <span className="status-badge">{t("supplierHistory.reversedBadge")}</span> : null}
                  </div>
                  {!reversal && !row.reversed_by_payment_id && reversing !== row.id ? (
                    <button className="text-button danger-link" disabled={busy} onClick={() => { setReversing(row.id); setReason(""); setNotice(undefined); }} type="button">{t("supplierLedger.reverse")}</button>
                  ) : null}
                </div>
                {reversing === row.id ? (
                  <div className="receipt-reversal">
                    <label className="field"><span>{t("invoiceEditor.reversalReason")}</span><input maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                    <ConfirmAction confirmLabel={t("supplierHistory.confirmReverse")} danger disabled={busy || !reason.trim()} label={t("supplierLedger.reverse")} onConfirm={() => reverse(row)}>{t("supplierHistory.reverseExplain")}</ConfirmAction>
                    <button className="text-button" onClick={() => { setReversing(null); setReason(""); }} type="button">{t("common.cancel")}</button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {data ? <Pagination onPage={setPage} page={page} totalPages={data.total_pages ?? 0} /> : null}
    </article>
  );
}
