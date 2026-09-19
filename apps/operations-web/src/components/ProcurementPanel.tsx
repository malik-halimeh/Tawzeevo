import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiBlobRequest, apiRequest } from "../api/client";
import type { ProductPriceBasis, TenantProduct, TenantProductListResponse } from "../api/types";
import { ErrorState } from "./Ui";

/**
 * Demand-driven procurement (PHASE_06.md E/F; D-058). A list is built from confirmed customer
 * demand; every line shows required (demand), target (owner), purchased (progress) and remaining
 * separately. Estimates are labelled and never booked. Nothing here is stock.
 */
interface Estimate { supplier_id: string; supplier_name: string; unit_cost: string; currency: string; age_days: number; is_stale: boolean; source_type: string; remaining_cost: string; supplier_is_recommended: boolean }
interface Line {
  id: string; product_id: string; product_name: string; supplier_id: string | null; supplier_name: string | null; price_basis: ProductPriceBasis; pieces_per_box: number | null;
  origin: "DEMAND" | "MANUAL" | "CARRY_FORWARD"; required_quantity: string; target_quantity: string; purchased_quantity: string; remaining_quantity: string; demand_invoice_count: number;
  removed_at: string | null; remove_reason: string | null; waived_at: string | null; waive_reason: string | null; carried_from_item_id: string | null; carried_to_item_id: string | null; notes: string | null; version: number; estimate: Estimate | null;
}
interface Assignee { membership_id: string; role: string; display_name: string; is_self: boolean }
interface ListDetail { id: string; status: string; title: string; demand_from: string | null; demand_to: string | null; notes: string | null; assignee: Assignee | null; carried_from_list_id: string | null; version: number; created_at: string; cancel_reason: string | null; items: Line[]; estimated_totals: Record<string, string>; open_line_count: number }
interface ListSummary { id: string; status: string; title: string; demand_from: string | null; demand_to: string | null; assignee: Assignee | null; created_at: string; line_count: number; open_line_count: number }
interface Supplier { id: string; name: string }

const today = () => new Date().toISOString().slice(0, 10);

export function ProcurementPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const q = `?tenant_id=${tenantId}`;
  const [lists, setLists] = useState<ListSummary[]>([]);
  const [detail, setDetail] = useState<ListDetail>();
  const [assignees, setAssignees] = useState<Assignee[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<TenantProduct[]>([]);
  const [from, setFrom] = useState(today());
  const [to, setTo] = useState(today());
  const [manualProduct, setManualProduct] = useState("");
  const [manualQty, setManualQty] = useState("");
  const [reason, setReason] = useState("");
  const [groupBySupplier, setGroupBySupplier] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const refresh = useCallback(async () => {
    const [page, people, sup, prod] = await Promise.all([
      apiRequest<{ lists: ListSummary[] }>(`/api/v1/procurement/lists${q}`),
      apiRequest<{ assignees: Assignee[] }>(`/api/v1/procurement/assignees${q}`),
      apiRequest<{ suppliers: Supplier[] }>(`/api/v1/suppliers${q}`),
      apiRequest<TenantProductListResponse>(`/api/v1/tenants/${tenantId}/products`),
    ]);
    setLists(page.lists); setAssignees(people.assignees); setSuppliers(sup.suppliers); setProducts(prod.products);
  }, [q, tenantId]);

  useEffect(() => { refresh().catch(setError); }, [refresh]);

  const run = (action: () => Promise<string | undefined>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    action().then((message) => { if (message) setNotice(message); }).catch(setError).finally(() => { setBusy(false); refresh().catch(setError); });
  };
  const open = (id: string) => run(async () => { setDetail(await apiRequest<ListDetail>(`/api/v1/procurement/lists/${id}${q}`)); return undefined; });
  const call = (path: string, init: RequestInit, message: string) => run(async () => {
    setDetail(await apiRequest<ListDetail>(`/api/v1/procurement/lists/${path}${q}`, init));
    return message;
  });

  const generate = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      setDetail(await apiRequest<ListDetail>(`/api/v1/procurement/lists${q}`, { method: "POST", body: JSON.stringify({ demand_from: from, demand_to: to }) }));
      return t("procurement.generated");
    });
  };
  const addManual = (event: FormEvent) => {
    event.preventDefault();
    if (!detail || !manualProduct || !manualQty) return;
    call(`${detail.id}/items`, { method: "POST", body: JSON.stringify({ product_id: manualProduct, target_quantity: manualQty }) }, t("procurement.lineAdded"));
    setManualQty("");
  };
  const editTarget = (line: Line, value: string) => {
    if (!detail || !value || value === line.target_quantity) return;
    call(`${detail.id}/items/${line.id}`, { method: "PATCH", body: JSON.stringify({ expected_version: line.version, target_quantity: value }) }, t("procurement.targetSaved"));
  };
  const chooseSupplier = (line: Line, supplierId: string) => {
    if (!detail) return;
    call(`${detail.id}/items/${line.id}`, { method: "PATCH", body: JSON.stringify(supplierId ? { expected_version: line.version, supplier_id: supplierId } : { expected_version: line.version, clear_supplier: true }) }, t("procurement.supplierSaved"));
  };

  const fmtUnit = (line: Line) => `${line.price_basis === "BOX" ? t("tenantWorkspace.box") : t("tenantWorkspace.piece")}${line.pieces_per_box ? ` ×${line.pieces_per_box}` : ""}`;
  const state = (line: Line) => line.removed_at ? "removed" : line.waived_at ? "waived" : line.carried_to_item_id ? "carried" : Number(line.remaining_quantity) === 0 && Number(line.purchased_quantity) > 0 ? "purchased" : "open";
  const editable = detail && (detail.status === "OPEN" || detail.status === "PARTIALLY_PURCHASED");
  const groups = detail ? Object.entries(detail.items.reduce<Record<string, Line[]>>((acc, line) => { const key = groupBySupplier ? (line.supplier_name ?? t("procurement.noSupplier")) : t("procurement.allLines"); (acc[key] ??= []).push(line); return acc; }, {})) : [];

  return (
    <section className="procurement-panel" aria-labelledby="procurement-title">
      <header>
        <p className="section-kicker">{t("procurement.kicker")}</p>
        <h3 id="procurement-title">{t("procurement.title")}</h3>
        <p>{t("procurement.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}

      <form className="inline-form" onSubmit={generate} aria-label={t("procurement.generate")}>
        <label className="field"><span>{t("procurement.demandFrom")}</span><input required type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
        <label className="field"><span>{t("procurement.demandTo")}</span><input required type="date" value={to} onChange={(event) => setTo(event.target.value)} /></label>
        <button className="button" disabled={busy} type="submit">{t("procurement.generate")}</button>
      </form>

      <div className="orders-layout">
        <ul className="outbox-list" aria-label={t("procurement.lists")}>
          {lists.length === 0 ? <li className="muted">{t("procurement.empty")}</li> : null}
          {lists.map((row) => (
            <li className="outbox-row" key={row.id}>
              <button aria-current={detail?.id === row.id ? "true" : undefined} className="text-button" onClick={() => open(row.id)} type="button">
                <strong>{row.title}</strong> · {row.open_line_count}/{row.line_count}{row.assignee ? ` · ${row.assignee.display_name}` : ""}
              </button>
              <span className="status-badge">{t(`procurement.status.${row.status}`)}</span>
            </li>
          ))}
        </ul>

        {detail ? (
          <article className="content-card procurement-detail" aria-label={detail.title}>
            <h4>{detail.title} <span className="status-badge">{t(`procurement.status.${detail.status}`)}</span></h4>
            {detail.demand_from ? <p className="muted">{t("procurement.demandRange", { from: detail.demand_from, to: detail.demand_to ?? detail.demand_from })}</p> : null}
            {detail.cancel_reason ? <p className="muted">{t("procurement.cancelledBecause", { reason: detail.cancel_reason })}</p> : null}
            <div className="category-actions procurement-toolbar">
              <label className="field"><span>{t("procurement.assignee")}</span>
                <select disabled={!editable || busy} value={detail.assignee?.membership_id ?? ""} onChange={(event) => call(`${detail.id}/assignee`, { method: "PUT", body: JSON.stringify({ membership_id: event.target.value || null }) }, t("procurement.assigneeSaved"))}>
                  <option value="">{t("procurement.unassigned")}</option>
                  {assignees.map((person) => <option key={person.membership_id} value={person.membership_id}>{person.display_name} · {t(`procurement.roles.${person.role}`)}{person.is_self ? ` (${t("procurement.me")})` : ""}</option>)}
                </select>
              </label>
              <label className="field checkbox"><input checked={groupBySupplier} type="checkbox" onChange={(event) => setGroupBySupplier(event.target.checked)} /> <span>{t("procurement.groupBySupplier")}</span></label>
              <button className="text-button" onClick={() => window.print()} type="button">{t("procurement.print")}</button>
              <button className="text-button" disabled={busy} onClick={() => run(async () => {
                const blob = await apiBlobRequest(`/api/v1/procurement/lists/${detail.id}/export.csv${q}`);
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a"); anchor.href = url; anchor.download = `procurement-${detail.id}.csv`; anchor.click();
                URL.revokeObjectURL(url);
                return undefined;
              })} type="button">{t("procurement.exportCsv")}</button>
            </div>
            <p className="muted">{t("procurement.estimateNote")}{Object.keys(detail.estimated_totals).length ? ` ${Object.entries(detail.estimated_totals).map(([currency, total]) => `${total} ${currency}`).join(" · ")}` : ""}</p>

            {groups.map(([group, lines]) => (
              <div className="procurement-group" key={group}>
                {groupBySupplier ? <h5>{group}</h5> : null}
                <table className="order-lines procurement-lines">
                  <thead><tr><th>{t("orders.item")}</th><th>{t("procurement.unit")}</th><th>{t("procurement.required")}</th><th>{t("procurement.target")}</th><th>{t("procurement.purchased")}</th><th>{t("procurement.remaining")}</th><th>{t("supplierSetup.supplier")}</th><th>{t("procurement.estimate")}</th><th>{t("procurement.state")}</th></tr></thead>
                  <tbody>
                    {lines.map((line) => (
                      <tr className={`line-${state(line)}`} key={line.id}>
                        <td>{line.product_name}{line.origin !== "DEMAND" ? <> <small className="muted">· {t(`procurement.origin.${line.origin}`)}</small></> : null}{line.demand_invoice_count ? <> <small className="muted">· {t("procurement.fromInvoices", { count: line.demand_invoice_count })}</small></> : null}</td>
                        <td>{fmtUnit(line)}</td>
                        <td dir="ltr">{line.required_quantity}</td>
                        <td dir="ltr">{editable && state(line) === "open" ? <input aria-label={t("procurement.targetFor", { product: line.product_name })} className="qty-input" defaultValue={line.target_quantity} dir="ltr" inputMode="decimal" min="0" step="0.0001" type="number" onBlur={(event) => editTarget(line, event.target.value)} /> : line.target_quantity}</td>
                        <td dir="ltr">{line.purchased_quantity}</td>
                        <td dir="ltr"><strong>{line.remaining_quantity}</strong></td>
                        <td>{editable && state(line) === "open" ? (
                          <select aria-label={t("procurement.supplierFor", { product: line.product_name })} value={line.supplier_id ?? ""} onChange={(event) => chooseSupplier(line, event.target.value)}>
                            <option value="">—</option>
                            {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
                          </select>
                        ) : (line.supplier_name ?? "—")}</td>
                        <td dir="ltr">{line.estimate ? <>{line.estimate.remaining_cost} {line.estimate.currency} <small className="muted">({line.estimate.unit_cost} · {line.estimate.supplier_is_recommended ? t("procurement.cheapest") : line.estimate.supplier_name} · {line.estimate.is_stale ? <mark>{t("supplierSetup.ageDays", { days: line.estimate.age_days })}</mark> : t("supplierSetup.ageDays", { days: line.estimate.age_days })})</small></> : <span className="muted">{t("procurement.noEstimate")}</span>}</td>
                        <td>
                          {t(`procurement.lineState.${state(line)}`)}
                          {line.remove_reason ? <small className="muted"> · {line.remove_reason}</small> : null}
                          {line.waive_reason ? <small className="muted"> · {line.waive_reason}</small> : null}
                          {editable && state(line) === "open" ? (
                            <span className="line-actions">
                              {" "}<button className="text-button" disabled={busy || !reason} onClick={() => call(`${detail.id}/items/${line.id}/waive`, { method: "POST", body: JSON.stringify({ reason }) }, t("procurement.waived"))} type="button">{t("procurement.waive")}</button>
                              {Number(line.purchased_quantity) === 0 ? <> {" "}<button className="text-button" disabled={busy || !reason} onClick={() => call(`${detail.id}/items/${line.id}/remove`, { method: "POST", body: JSON.stringify({ reason }) }, t("procurement.removed"))} type="button">{t("procurement.remove")}</button></> : null}
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}

            {editable ? (
              <>
                <form className="inline-form" onSubmit={addManual}>
                  <label className="field"><span>{t("procurement.manualProduct")}</span>
                    <select required value={manualProduct} onChange={(event) => setManualProduct(event.target.value)}>
                      <option value="">—</option>
                      {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
                    </select>
                  </label>
                  <label className="field"><span>{t("procurement.target")}</span><input dir="ltr" inputMode="decimal" min="0.0001" required step="0.0001" type="number" value={manualQty} onChange={(event) => setManualQty(event.target.value)} /></label>
                  <button className="button" disabled={busy} type="submit">{t("procurement.addLine")}</button>
                </form>
                <label className="field field-wide"><span>{t("procurement.reason")}</span><input maxLength={300} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                <div className="category-actions">
                  <button className="button" disabled={busy} onClick={() => call(`${detail.id}/complete`, { method: "POST" }, t("procurement.completed"))} type="button">{t("procurement.complete")}</button>
                  <button className="button" disabled={busy || detail.open_line_count === 0} onClick={() => run(async () => { setDetail(await apiRequest<ListDetail>(`/api/v1/procurement/lists/${detail.id}/carry-forward${q}`, { method: "POST", body: JSON.stringify({}) })); return t("procurement.carried"); })} type="button">{t("procurement.carryForward")}</button>
                  <button className="text-button" disabled={busy || !reason} onClick={() => call(`${detail.id}/cancel`, { method: "POST", body: JSON.stringify({ reason }) }, t("procurement.cancelled"))} type="button">{t("procurement.cancel")}</button>
                </div>
                <p className="muted">{t("procurement.completeRule")}</p>
              </>
            ) : null}
          </article>
        ) : <p className="muted">{t("procurement.pick")}</p>}
      </div>
    </section>
  );
}
