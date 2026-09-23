import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { ErrorState } from "./Ui";
import type { Supplier } from "./SupplierSetup";
import { useKeepFocus } from "./useKeepFocus";

interface SupplierBalances {
  supplier_id: string;
  balances: { currency: string; balance: string }[];
}

interface SupplierPayment {
  id: string;
  direction: string;
  currency: string;
  amount: string;
  prepayment: boolean;
  reverses_payment_id: string | null;
}

/**
 * Owner supplier ledger desk: opening payable, ordinary payments (capped at the payable, D-039),
 * explicit prepayments (labelled credit) and compensating reversals. Aggregate per currency only.
 */
export function SupplierLedgerPanel({ tenantId, suppliers }: { tenantId: string; suppliers: Supplier[] }) {
  const { t } = useTranslation();
  const [supplierId, setSupplierId] = useState("");
  const [balances, setBalances] = useState<SupplierBalances>();
  const [currency, setCurrency] = useState("USD");
  const [openingAmount, setOpeningAmount] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("CASH");
  const [lastPayment, setLastPayment] = useState<SupplierPayment>();
  const [reversalReason, setReversalReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const root = useRef<HTMLElement>(null);
  useKeepFocus(busy, root);

  const run = useCallback(async (operation: () => Promise<void>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    try { await operation(); } catch (caught) { setError(caught); } finally { setBusy(false); }
  }, []);

  const loadBalances = useCallback(async (id: string) => {
    if (!id) { setBalances(undefined); return; }
    setBalances(await apiRequest<SupplierBalances>(`/api/v1/supplier-ledger/${id}/balances?tenant_id=${tenantId}`));
  }, [tenantId]);

  useEffect(() => { void run(() => loadBalances(supplierId)); }, [run, loadBalances, supplierId]);

  const recordOpening = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      await apiRequest(`/api/v1/supplier-ledger/opening-balances?tenant_id=${tenantId}`, {
        method: "POST",
        body: JSON.stringify({ idempotency_key: crypto.randomUUID(), supplier_id: supplierId, currency, signed_amount: openingAmount, effective_at: new Date().toISOString() }),
      });
      setOpeningAmount("");
      await loadBalances(supplierId);
      setNotice(t("supplierLedger.openingSaved"));
    });
  };

  const pay = (prepayment: boolean) => (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const payment = await apiRequest<SupplierPayment>(`/api/v1/payments/${prepayment ? "supplier-prepayments" : "supplier-payments"}?tenant_id=${tenantId}`, {
        method: "POST",
        body: JSON.stringify({ idempotency_key: crypto.randomUUID(), supplier_id: supplierId, currency, amount: paymentAmount, paid_at: new Date().toISOString(), method: paymentMethod || null }),
      });
      setLastPayment(payment);
      setPaymentAmount("");
      await loadBalances(supplierId);
      setNotice(t(prepayment ? "supplierLedger.prepaymentSaved" : "supplierLedger.paymentSaved"));
    });
  };

  const reverse = () => {
    if (!lastPayment) return;
    void run(async () => {
      await apiRequest<SupplierPayment>(`/api/v1/payments/supplier-payments/${lastPayment.id}/reverse?tenant_id=${tenantId}`, {
        method: "POST",
        body: JSON.stringify({ idempotency_key: crypto.randomUUID(), reason: reversalReason }),
      });
      setLastPayment(undefined); setReversalReason("");
      await loadBalances(supplierId);
      setNotice(t("supplierLedger.reversed"));
    });
  };

  return (
    <article className="panel supplier-ledger" aria-labelledby="supplier-ledger-title" ref={root}>
      <h4 id="supplier-ledger-title">{t("supplierLedger.title")}</h4>
      <p className="backend-note">{t("supplierLedger.body")}</p>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      <label className="field"><span>{t("supplierSetup.supplier")}</span>
        <select value={supplierId} onChange={(event) => { setSupplierId(event.target.value); setLastPayment(undefined); }}>
          <option value="">—</option>
          {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
        </select>
      </label>
      {supplierId ? (
        <>
          <dl className="supplier-balances">
            {balances?.balances.length ? balances.balances.map((row) => (
              <div key={row.currency}><dt>{t("supplierLedger.payable")} · {row.currency}</dt><dd dir="ltr">{row.balance}</dd></div>
            )) : <div><dt>{t("supplierLedger.payable")}</dt><dd>{t("supplierLedger.noBalance")}</dd></div>}
          </dl>
          <label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label>
          <form className="inline-form" onSubmit={recordOpening}>
            <label className="field"><span>{t("supplierLedger.openingAmount")}</span><input dir="ltr" required step="0.0001" type="number" value={openingAmount} onChange={(event) => setOpeningAmount(event.target.value)} /></label>
            <button className="button secondary-button" disabled={busy} type="submit">{t("supplierLedger.recordOpening")}</button>
          </form>
          <form className="inline-form" onSubmit={pay(false)}>
            <label className="field"><span>{t("supplierLedger.paymentAmount")}</span><input dir="ltr" min="0.0001" required step="0.0001" type="number" value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} /></label>
            <label className="field"><span>{t("invoiceEditor.paymentMethod")}</span><input value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)} /></label>
            <button className="button" disabled={busy} type="submit">{t("supplierLedger.recordPayment")}</button>
            <button className="button secondary-button" disabled={busy || !paymentAmount} onClick={pay(true)} type="button">{t("supplierLedger.recordPrepayment")}</button>
          </form>
          {lastPayment ? (
            <div className="payment-slip" aria-live="polite">
              <div><span>{t(lastPayment.prepayment ? "supplierLedger.prepaymentLabel" : "supplierLedger.paymentLabel")}</span><strong dir="ltr">{lastPayment.amount} {lastPayment.currency}</strong></div>
              <div className="receipt-reversal">
                <label className="field"><span>{t("invoiceEditor.reversalReason")}</span><input value={reversalReason} onChange={(event) => setReversalReason(event.target.value)} /></label>
                <button className="text-button danger-link" disabled={busy || !reversalReason.trim()} onClick={reverse} type="button">{t("supplierLedger.reverse")}</button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </article>
  );
}
