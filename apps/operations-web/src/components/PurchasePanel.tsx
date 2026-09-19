import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis, TenantProduct, TenantProductListResponse } from "../api/types";
import { browserOffline } from "../offline/network";
import { queuePurchase } from "../offline/supplierCommands";
import { ErrorState } from "./Ui";

/**
 * Actual supplier purchases (PHASE_06.md G/H). One immutable purchase writes the price history,
 * the supplier payable and the procurement progress together. A reversal is a compensating
 * ledger entry; the purchase stays readable. Totals are per currency and never added together.
 */
interface PurchaseLine { id: string; line_number: number; product_id: string; product_name: string; procurement_item_id: string | null; quantity: string; price_basis: ProductPriceBasis; pieces_per_box: number | null; unit_cost: string; line_total: string }
interface Purchase { id: string; supplier_id: string; supplier_name: string; procurement_list_id: string | null; purchased_at: string; currency: string; total_amount: string; supplier_reference: string | null; reversed_at: string | null; reversal_reason: string | null; replayed: boolean; items: PurchaseLine[] }
interface CurrencyTotal { currency: string; outstanding: string; credit: string; parties: number }
interface Totals { customers: CurrencyTotal[]; suppliers: CurrencyTotal[] }
interface OpenLine { id: string; product_id: string; product_name: string; supplier_id: string | null; remaining_quantity: string; price_basis: ProductPriceBasis; removed_at: string | null; waived_at: string | null; carried_to_item_id: string | null }
interface ListSummary { id: string; status: string; title: string }
interface DraftLine { product_id: string; quantity: string; unit_cost: string; procurement_item_id: string | null }

export function PurchasePanel({ tenantId, membershipId, suppliers }: { tenantId: string; membershipId?: string | undefined; suppliers: { id: string; name: string }[] }) {
  const { t } = useTranslation();
  const q = `?tenant_id=${tenantId}`;
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [totals, setTotals] = useState<Totals>();
  const [products, setProducts] = useState<TenantProduct[]>([]);
  const [lists, setLists] = useState<ListSummary[]>([]);
  const [openLines, setOpenLines] = useState<OpenLine[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [listId, setListId] = useState("");
  const [reference, setReference] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([{ product_id: "", quantity: "", unit_cost: "", procurement_item_id: null }]);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const refresh = useCallback(async () => {
    const [page, sums, prod, open] = await Promise.all([
      apiRequest<{ purchases: Purchase[] }>(`/api/v1/supplier-purchases${q}`),
      apiRequest<Totals>(`/api/v1/supplier-ledger/totals${q}`),
      apiRequest<TenantProductListResponse>(`/api/v1/tenants/${tenantId}/products`),
      apiRequest<{ lists: ListSummary[] }>(`/api/v1/procurement/lists${q}`),
    ]);
    setPurchases(page.purchases); setTotals(sums); setProducts(prod.products);
    setLists(open.lists.filter((row) => row.status === "OPEN" || row.status === "PARTIALLY_PURCHASED"));
  }, [q, tenantId]);
  useEffect(() => { refresh().catch(setError); }, [refresh]);

  // Picking a procurement list preloads its open lines for this supplier as purchase lines.
  useEffect(() => {
    if (!listId) { setOpenLines([]); return; }
    apiRequest<{ items: OpenLine[] }>(`/api/v1/procurement/lists/${listId}${q}`)
      .then((detail) => {
        const open = detail.items.filter((row) => !row.removed_at && !row.waived_at && !row.carried_to_item_id && Number(row.remaining_quantity) > 0);
        setOpenLines(open);
        const mine = open.filter((row) => !supplierId || row.supplier_id === supplierId);
        if (mine.length) setLines(mine.map((row) => ({ product_id: row.product_id, quantity: row.remaining_quantity, unit_cost: "", procurement_item_id: row.id })));
      })
      .catch(setError);
  }, [listId, supplierId, q]);

  const currency = products.find((p) => p.id === lines[0]?.product_id)?.currency ?? "USD";
  const setLine = (index: number, patch: Partial<DraftLine>) => setLines((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(undefined); setNotice(undefined);
    const input = {
      idempotency_key: key, supplier_id: supplierId, currency, procurement_list_id: listId || null, supplier_reference: reference || null,
      items: lines.filter((row) => row.product_id && row.quantity && row.unit_cost !== "").map((row) => ({ product_id: row.product_id, quantity: row.quantity, unit_cost: row.unit_cost, procurement_item_id: row.procurement_item_id })),
    };
    const reset = () => { setKey(crypto.randomUUID()); setLines([{ product_id: "", quantity: "", unit_cost: "", procurement_item_id: null }]); setReference(""); setListId(""); };
    apiRequest<Purchase>(`/api/v1/supplier-purchases${q}`, { method: "POST", body: JSON.stringify(input) })
      .then((purchase) => {
        setNotice(purchase.replayed ? t("purchases.replayed") : t("purchases.recorded", { total: purchase.total_amount, currency: purchase.currency }));
        reset();
        return refresh();
      })
      .catch(async (problem: unknown) => {
        // Offline: the purchase keeps its idempotency key as the operation id and is sent exactly once later.
        if (!(problem instanceof TypeError) || !browserOffline() || !membershipId) { setError(problem); return; }
        await queuePurchase(tenantId, membershipId, input);
        setNotice(t("purchases.queued"));
        reset();
      })
      .finally(() => setBusy(false));
  };

  const reverse = (purchase: Purchase) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest<Purchase>(`/api/v1/supplier-purchases/${purchase.id}/reverse${q}`, { method: "POST", body: JSON.stringify({ idempotency_key: crypto.randomUUID(), reason }) })
      .then(() => { setNotice(t("purchases.reversed")); setReason(""); return refresh(); })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  return (
    <article className="panel purchase-panel" aria-labelledby="purchases-title">
      <h4 id="purchases-title">{t("purchases.title")}</h4>
      <p className="backend-note">{t("purchases.body")}</p>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}

      {totals ? (
        <dl className="supplier-balances totals" aria-label={t("purchases.totalsTitle")}>
          {totals.suppliers.map((row) => <div key={`s-${row.currency}`}><dt>{t("purchases.supplierPayable")} · {row.currency}</dt><dd dir="ltr">{row.outstanding}{Number(row.credit) > 0 ? ` (${t("purchases.credit")} ${row.credit})` : ""}</dd></div>)}
          {totals.customers.map((row) => <div key={`c-${row.currency}`}><dt>{t("purchases.customerOutstanding")} · {row.currency}</dt><dd dir="ltr">{row.outstanding}{Number(row.credit) > 0 ? ` (${t("purchases.credit")} ${row.credit})` : ""}</dd></div>)}
          {totals.suppliers.length === 0 && totals.customers.length === 0 ? <div><dt>{t("purchases.totalsTitle")}</dt><dd>{t("supplierLedger.noBalance")}</dd></div> : null}
        </dl>
      ) : null}

      <form className="form-grid purchase-form" onSubmit={submit} aria-label={t("purchases.record")}>
        <label className="field"><span>{t("supplierSetup.supplier")}</span>
          <select required value={supplierId} onChange={(event) => setSupplierId(event.target.value)}>
            <option value="">—</option>
            {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("purchases.fromList")}</span>
          <select value={listId} onChange={(event) => setListId(event.target.value)}>
            <option value="">{t("purchases.noList")}</option>
            {lists.map((row) => <option key={row.id} value={row.id}>{row.title}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("purchases.reference")}</span><input maxLength={200} value={reference} onChange={(event) => setReference(event.target.value)} /></label>
        <table className="order-lines purchase-lines">
          <thead><tr><th>{t("orders.item")}</th><th>{t("invoiceEditor.quantity")}</th><th>{t("supplierSetup.unitCost")} ({currency})</th><th /></tr></thead>
          <tbody>
            {lines.map((row, index) => (
              <tr key={index}>
                <td>
                  <select aria-label={t("purchases.lineProduct", { n: index + 1 })} required value={row.product_id} onChange={(event) => setLine(index, { product_id: event.target.value, procurement_item_id: openLines.find((o) => o.product_id === event.target.value)?.id ?? null })}>
                    <option value="">—</option>
                    {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                  </select>
                </td>
                <td><input aria-label={t("purchases.lineQuantity", { n: index + 1 })} dir="ltr" inputMode="decimal" min="0.0001" required step="0.0001" type="number" value={row.quantity} onChange={(event) => setLine(index, { quantity: event.target.value })} /></td>
                <td><input aria-label={t("purchases.lineCost", { n: index + 1 })} dir="ltr" inputMode="decimal" min="0" required step="0.0001" type="number" value={row.unit_cost} onChange={(event) => setLine(index, { unit_cost: event.target.value })} /></td>
                <td>{lines.length > 1 ? <button className="text-button" onClick={() => setLines((current) => current.filter((_, i) => i !== index))} type="button">{t("common.remove")}</button> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="category-actions">
          <button className="text-button" onClick={() => setLines((current) => [...current, { product_id: "", quantity: "", unit_cost: "", procurement_item_id: null }])} type="button">{t("purchases.addLine")}</button>
          <button className="button" disabled={busy || !supplierId} type="submit">{t("purchases.record")}</button>
        </div>
      </form>

      {purchases.length > 0 ? (
        <>
          <h5>{t("purchases.history")}</h5>
          <label className="field field-wide"><span>{t("invoiceEditor.reversalReason")}</span><input maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <ul className="outbox-list purchase-history">
            {purchases.map((purchase) => (
              <li className="outbox-row" key={purchase.id}>
                <span>
                  <strong>{purchase.supplier_name}</strong> · <bdi dir="ltr">{purchase.total_amount} {purchase.currency}</bdi> · <time dateTime={purchase.purchased_at}>{new Date(purchase.purchased_at).toLocaleDateString()}</time>
                  {purchase.supplier_reference ? <> · {purchase.supplier_reference}</> : null}
                  <small className="muted"> · {purchase.items.map((line) => `${line.quantity} × ${line.product_name}`).join(", ")}</small>
                  {purchase.reversed_at ? <> · <span className="status-badge">{t("purchases.reversedBadge")}</span> <small className="muted">{purchase.reversal_reason}</small></> : null}
                </span>
                {!purchase.reversed_at ? <button className="text-button danger-link" disabled={busy || !reason.trim()} onClick={() => reverse(purchase)} type="button">{t("purchases.reverse")}</button> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}
