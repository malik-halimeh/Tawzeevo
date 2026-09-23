import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis, TenantProduct, TenantProductListResponse } from "../api/types";
import { browserOffline } from "../offline/network";
import { queueCostAppend } from "../offline/supplierCommands";
import { ErrorState } from "./Ui";
import { PurchasePanel } from "./PurchasePanel";
import { SupplierLedgerPanel } from "./SupplierLedgerPanel";
import { useKeepFocus } from "./useKeepFocus";

export interface Supplier {
  id: string;
  tenant_id: string;
  name: string;
  contact_name: string | null;
  contact_phone: string | null;
  address: string | null;
  latitude: string | null;
  longitude: string | null;
  notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

/** Editable profile fields (PHASE_06.md B); blank strings are sent as null. */
interface SupplierProfileDraft { name: string; contact_name: string; contact_phone: string; address: string; latitude: string; longitude: string; notes: string }
const emptyProfile = (): SupplierProfileDraft => ({ name: "", contact_name: "", contact_phone: "", address: "", latitude: "", longitude: "", notes: "" });
const profileOf = (supplier: Supplier): SupplierProfileDraft => ({
  name: supplier.name, contact_name: supplier.contact_name ?? "", contact_phone: supplier.contact_phone ?? "", address: supplier.address ?? "",
  latitude: supplier.latitude ?? "", longitude: supplier.longitude ?? "", notes: supplier.notes ?? "",
});
const profileBody = (draft: SupplierProfileDraft) => ({
  name: draft.name.trim(), contact_name: draft.contact_name.trim() || null, contact_phone: draft.contact_phone.trim() || null, address: draft.address.trim() || null,
  latitude: draft.latitude.trim() || null, longitude: draft.longitude.trim() || null, notes: draft.notes.trim() || null,
});

/** Derived per supplier and comparable group; nothing here is stored (PHASE_06.md C). */
interface PriceInsight {
  supplier_id: string; supplier_name: string; currency: string; cost_basis: ProductPriceBasis; pieces_per_box: number | null;
  latest_unit_cost: string; latest_effective_at: string; latest_source_type: string; age_days: number;
  lowest_unit_cost: string; highest_unit_cost: string; last_purchase_at: string | null; last_purchase_unit_cost: string | null;
  recent_unit_costs: string[]; entry_count: number; variation_percent: string | null; stability: "STABLE" | "MODERATE" | "VOLATILE" | "INSUFFICIENT_DATA"; is_preferred: boolean;
}
interface PriceInsights { product_id: string; stale_after_days: number; insights: PriceInsight[] }

/** Deterministic comparable ranking plus the owner's override (PHASE_06.md D). */
interface RankedSupplier { rank: number; supplier_id: string; supplier_name: string; unit_cost: string; effective_at: string; age_days: number; is_stale: boolean; source_type: string; entry_id: string; quantity_context: string | null; delta_vs_best: string; explanation: string }
interface ExcludedSupplier { supplier_id: string; supplier_name: string; reason: string; detail: string }
interface Recommendation {
  product_id: string; currency: string; cost_basis: ProductPriceBasis; pieces_per_box: number | null; stale_after_days: number;
  recommended_supplier_id: string | null; preferred_supplier_id: string | null; effective_supplier_id: string | null; effective_reason: string;
  ranked: RankedSupplier[]; excluded: ExcludedSupplier[];
}

interface ProductCostEntry {
  id: string;
  supplier_id: string;
  unit_cost: string;
  currency: string;
  cost_basis: ProductPriceBasis;
  pieces_per_box: number | null;
  effective_at: string;
  source_type: string;
  quantity_context: string | null;
  notes: string | null;
  created_at: string;
}

interface ProductCostSetup {
  product_id: string;
  product_name: string;
  currency: string;
  preferred_supplier_id: string | null;
  entries: ProductCostEntry[];
}

/**
 * Owner setup for tenant-private suppliers and append-only product costs (D-041 / D-034).
 * Costs are never edited here: every save appends a new effective-dated entry.
 */
export function SupplierSetup({ tenantId, membershipId, initialProductId }: { tenantId: string; membershipId?: string; initialProductId?: string }) {
  const { t } = useTranslation();
  // Undefined until the first answer, so "no suppliers yet" is never shown while the list is still loading.
  const [loadedSuppliers, setSuppliers] = useState<Supplier[]>();
  const suppliers = loadedSuppliers ?? [];
  const [products, setProducts] = useState<TenantProduct[]>([]);
  const [profile, setProfile] = useState<SupplierProfileDraft>(emptyProfile());
  const [editing, setEditing] = useState<{ id: string; version: number; draft: SupplierProfileDraft }>();
  const [insights, setInsights] = useState<PriceInsights>();
  const [recommendation, setRecommendation] = useState<Recommendation>();
  const [compareBasis, setCompareBasis] = useState<ProductPriceBasis | "">("");
  const [overrideReason, setOverrideReason] = useState("");
  const [productId, setProductId] = useState(initialProductId ?? "");
  const [setup, setSetup] = useState<ProductCostSetup>();
  const [costSupplierId, setCostSupplierId] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [basis, setBasis] = useState<ProductPriceBasis>("PIECE");
  const [piecesPerBox, setPiecesPerBox] = useState("");
  const [notes, setNotes] = useState("");
  const [sourceType, setSourceType] = useState<"MANUAL" | "QUOTE">("MANUAL");
  const [quantityContext, setQuantityContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const root = useRef<HTMLElement>(null);
  useKeepFocus(busy, root);

  const run = useCallback(async (operation: () => Promise<void>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    try { await operation(); } catch (caught) { setError(caught); } finally { setBusy(false); }
  }, []);

  const loadSuppliers = useCallback(async () => {
    const response = await apiRequest<{ suppliers: Supplier[] }>(`/api/v1/suppliers?tenant_id=${tenantId}`);
    setSuppliers(response.suppliers);
  }, [tenantId]);

  const loadProducts = useCallback(async () => {
    const response = await apiRequest<TenantProductListResponse>(`/api/v1/tenants/${tenantId}/products`);
    setProducts(response.products);
  }, [tenantId]);

  const recommendationPath = useCallback((id: string) => `/api/v1/supplier-prices/products/${id}/recommendation?tenant_id=${tenantId}${compareBasis ? `&cost_basis=${compareBasis}` : ""}`, [tenantId, compareBasis]);

  const loadSetup = useCallback(async (id: string) => {
    if (!id) { setSetup(undefined); setInsights(undefined); setRecommendation(undefined); return; }
    const [costs, derived, ranking] = await Promise.all([
      apiRequest<ProductCostSetup>(`/api/v1/suppliers/products/${id}/costs?tenant_id=${tenantId}`),
      apiRequest<PriceInsights>(`/api/v1/supplier-prices/products/${id}?tenant_id=${tenantId}`),
      apiRequest<Recommendation>(recommendationPath(id)),
    ]);
    setSetup(costs); setInsights(derived); setRecommendation(ranking);
  }, [tenantId, recommendationPath]);

  useEffect(() => { void run(async () => { await Promise.all([loadSuppliers(), loadProducts()]); }); }, [run, loadSuppliers, loadProducts]);
  useEffect(() => { void run(() => loadSetup(productId)); }, [run, loadSetup, productId]);

  const product = products.find((item) => item.id === productId);

  const createSupplier = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      await apiRequest<Supplier>(`/api/v1/suppliers?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify(profileBody(profile)) });
      setProfile(emptyProfile());
      await loadSuppliers();
      setNotice(t("supplierSetup.supplierCreated"));
    });
  };

  const saveProfile = (event: FormEvent) => {
    event.preventDefault();
    if (!editing) return;
    void run(async () => {
      // expected_version: a change made on another device is a conflict, never a silent overwrite.
      await apiRequest<Supplier>(`/api/v1/suppliers/${editing.id}?tenant_id=${tenantId}`, { method: "PATCH", body: JSON.stringify({ ...profileBody(editing.draft), expected_version: editing.version }) });
      setEditing(undefined);
      await loadSuppliers();
      setNotice(t("supplierSetup.supplierSaved"));
    });
  };

  const appendCost = (event: FormEvent) => {
    event.preventDefault();
    if (!product) return;
    void run(async () => {
      const body = {
        supplier_id: costSupplierId,
        unit_cost: unitCost,
        currency: product.currency,
        cost_basis: basis,
        pieces_per_box: piecesPerBox ? Number(piecesPerBox) : null,
        source_type: sourceType,
        quantity_context: quantityContext || null,
        notes: notes || null,
      };
      let response: ProductCostSetup;
      try {
        response = await apiRequest<ProductCostSetup>(`/api/v1/suppliers/products/${product.id}/costs?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify(body) });
      } catch (problem) {
        // No connection: queue the append on this device; it is sent once on reconnect (PHASE_06.md I).
        if (!(problem instanceof TypeError) || !browserOffline() || !membershipId) throw problem;
        await queueCostAppend(tenantId, membershipId, { product_id: product.id, ...body });
        setUnitCost(""); setNotes(""); setQuantityContext("");
        setNotice(t("supplierSetup.costQueued"));
        return;
      }
      setSetup(response);
      setInsights(await apiRequest<PriceInsights>(`/api/v1/supplier-prices/products/${product.id}?tenant_id=${tenantId}`));
      setRecommendation(await apiRequest<Recommendation>(recommendationPath(product.id)));
      setUnitCost(""); setNotes(""); setQuantityContext("");
      setNotice(t("supplierSetup.costAppended"));
    });
  };

  const setPreferred = (supplierId: string | null, reason?: string) => {
    if (!product) return;
    void run(async () => {
      setSetup(await apiRequest<ProductCostSetup>(`/api/v1/suppliers/products/${product.id}/preferred-supplier?tenant_id=${tenantId}`, {
        method: "PUT",
        body: JSON.stringify({ supplier_id: supplierId, reason: reason?.trim() || null }),
      }));
      setRecommendation(await apiRequest<Recommendation>(recommendationPath(product.id)));
      setOverrideReason("");
      setNotice(t("supplierSetup.preferredSaved"));
    });
  };

  const supplierName_ = (id: string) => suppliers.find((supplier) => supplier.id === id)?.name ?? "—";

  return (
    <section className="supplier-setup" aria-labelledby="supplier-setup-title" ref={root}>
      <header>
        <p className="section-kicker">{t("supplierSetup.kicker")}</p>
        <h3 id="supplier-setup-title">{t("supplierSetup.title")}</h3>
        <p>{t("supplierSetup.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}

      <div className="supplier-setup-grid">
        <article className="panel">
          <h4>{t("supplierSetup.suppliers")}</h4>
          <form className="form-grid supplier-profile" onSubmit={createSupplier}>
            <ProfileFields draft={profile} idPrefix="new" onChange={setProfile} />
            <button className="button" disabled={busy} type="submit">{t("supplierSetup.addSupplier")}</button>
          </form>
          {loadedSuppliers === undefined ? (error ? null : <p className="empty-note">{t("common.loading")}</p>) : suppliers.length === 0 ? <p className="empty-note">{t("supplierSetup.noSuppliers")}</p> : (
            <ul className="supplier-list">
              {suppliers.map((supplier) => (
                <li key={supplier.id}>
                  {editing?.id === supplier.id ? (
                    <form className="form-grid supplier-profile" onSubmit={saveProfile} aria-label={t("supplierSetup.editSupplier", { name: supplier.name })}>
                      <ProfileFields draft={editing.draft} idPrefix={supplier.id} onChange={(draft) => setEditing({ ...editing, draft })} />
                      <div className="category-actions">
                        <button className="button" disabled={busy} type="submit">{t("common.saveChanges")}</button>
                        <button className="text-button" onClick={() => setEditing(undefined)} type="button">{t("common.cancel")}</button>
                      </div>
                    </form>
                  ) : (
                    <div className="supplier-row">
                      <div>
                        <strong>{supplier.name}</strong>
                        {supplier.contact_name || supplier.contact_phone ? <span className="muted"> · {supplier.contact_name}{supplier.contact_phone ? <> <bdi dir="ltr">{supplier.contact_phone}</bdi></> : null}</span> : null}
                        {supplier.address ? <span className="muted"> · {supplier.address}</span> : null}
                        {supplier.latitude && supplier.longitude ? <span className="muted"> · <bdi dir="ltr">{supplier.latitude}, {supplier.longitude}</bdi></span> : null}
                      </div>
                      <button className="text-button" disabled={busy} onClick={() => setEditing({ id: supplier.id, version: supplier.version, draft: profileOf(supplier) })} type="button">{t("supplierSetup.edit")}</button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="panel">
          <h4>{t("supplierSetup.productCosts")}</h4>
          <label className="field"><span>{t("supplierSetup.product")}</span>
            <select value={productId} onChange={(event) => setProductId(event.target.value)}>
              <option value="">{t("supplierSetup.chooseProduct")}</option>
              {products.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.unit_price} {item.currency}</option>)}
            </select>
          </label>
          {product && setup ? (
            <>
              <p className="backend-note">{t("supplierSetup.preferredSupplier")}: <strong>{setup.preferred_supplier_id ? supplierName_(setup.preferred_supplier_id) : t("supplierSetup.none")}</strong></p>
              <form className="inline-form cost-form" onSubmit={appendCost}>
                <label className="field"><span>{t("supplierSetup.supplier")}</span>
                  <select required value={costSupplierId} onChange={(event) => setCostSupplierId(event.target.value)}>
                    <option value="">—</option>
                    {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
                  </select>
                </label>
                <label className="field"><span>{t("supplierSetup.unitCost")} ({product.currency})</span><input dir="ltr" min="0" required step="0.0001" type="number" value={unitCost} onChange={(event) => setUnitCost(event.target.value)} /></label>
                <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span>
                  <select value={basis} onChange={(event) => setBasis(event.target.value as ProductPriceBasis)}>
                    <option value="PIECE">{t("tenantWorkspace.piece")}</option>
                    <option value="BOX">{t("tenantWorkspace.box")}</option>
                  </select>
                </label>
                {basis === "BOX" ? <label className="field"><span>{t("tenantWorkspace.piecesPerBox")}</span><input dir="ltr" min="1" type="number" value={piecesPerBox} placeholder={product.pieces_per_box ? String(product.pieces_per_box) : ""} onChange={(event) => setPiecesPerBox(event.target.value)} /></label> : null}
                <label className="field"><span>{t("supplierSetup.source")}</span>
                  <select value={sourceType} onChange={(event) => setSourceType(event.target.value as "MANUAL" | "QUOTE")}>
                    <option value="MANUAL">{t("supplierSetup.sources.MANUAL")}</option>
                    <option value="QUOTE">{t("supplierSetup.sources.QUOTE")}</option>
                  </select>
                </label>
                <label className="field"><span>{t("supplierSetup.quantityContext")}</span><input dir="ltr" min="0" step="0.0001" type="number" value={quantityContext} onChange={(event) => setQuantityContext(event.target.value)} /></label>
                <label className="field field-wide"><span>{t("supplierSetup.notes")}</span><input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
                <button className="button" disabled={busy || suppliers.length === 0} type="submit">{t("supplierSetup.appendCost")}</button>
              </form>
              {suppliers.length === 0 ? <p className="empty-note">{t("supplierSetup.createSupplierFirst")}</p> : null}
              {setup.entries.length === 0 ? <p className="empty-note">{t("supplierSetup.noCosts")}</p> : (
                // A real table: on a narrow screen it scrolls inside its own region instead of widening the page.
                <div aria-label={t("supplierSetup.productCosts")} className="table-region" role="region" tabIndex={0}>
                  <table className="cost-history">
                    <thead><tr><th>{t("supplierSetup.supplier")}</th><th>{t("supplierSetup.unitCost")}</th><th>{t("tenantWorkspace.priceBasis")}</th><th>{t("supplierSetup.effectiveAt")}</th><th>{t("supplierSetup.source")}</th><th /></tr></thead>
                    <tbody>
                      {setup.entries.map((entry) => (
                        <tr key={entry.id}>
                          <td>{supplierName_(entry.supplier_id)}{setup.preferred_supplier_id === entry.supplier_id ? ` · ${t("invoiceEditor.preferred")}` : ""}</td>
                          <td dir="ltr">{entry.unit_cost} {entry.currency}</td>
                          <td>{entry.cost_basis}{entry.pieces_per_box ? ` ×${entry.pieces_per_box}` : ""}</td>
                          <td><time dateTime={entry.effective_at}>{new Date(entry.effective_at).toLocaleString()}</time></td>
                          <td>{t(`supplierSetup.sources.${entry.source_type}`, { defaultValue: entry.source_type })}{entry.quantity_context ? ` · ${t("supplierSetup.forQuantity", { quantity: entry.quantity_context })}` : ""}</td>
                          <td>{setup.preferred_supplier_id !== entry.supplier_id ? <button className="text-button" disabled={busy} onClick={() => setPreferred(entry.supplier_id)} type="button">{t("supplierSetup.makePreferred")}</button> : null}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {setup.preferred_supplier_id ? <button className="text-button" disabled={busy} onClick={() => setPreferred(null)} type="button">{t("supplierSetup.clearPreferred")}</button> : null}
              {recommendation ? (
                <div className="price-insights supplier-recommendation" aria-labelledby="recommendation-title">
                  <h5 id="recommendation-title">{t("supplierSetup.recommendationTitle")}</h5>
                  <p className="muted">{t("supplierSetup.recommendationBody")}</p>
                  <label className="field"><span>{t("supplierSetup.compareGroup")}</span>
                    <select value={compareBasis} onChange={(event) => setCompareBasis(event.target.value as ProductPriceBasis | "")}>
                      <option value="">{t("supplierSetup.productUnit", { unit: product.price_basis === "BOX" ? t("tenantWorkspace.box") : t("tenantWorkspace.piece") })}</option>
                      <option value="PIECE">{t("tenantWorkspace.piece")}</option>
                      <option value="BOX">{t("tenantWorkspace.box")}</option>
                    </select>
                  </label>
                  <p className="form-status" role="status">
                    {recommendation.effective_reason === "NO_COMPARABLE_PRICE" ? t("supplierSetup.noComparable") : t(`supplierSetup.effective.${recommendation.effective_reason}`, {
                      supplier: supplierName_(recommendation.effective_supplier_id ?? ""),
                      recommended: supplierName_(recommendation.recommended_supplier_id ?? ""),
                    })}
                  </p>
                  {recommendation.ranked.length > 0 ? (
                    <ol className="ranking" aria-label={t("supplierSetup.recommendationTitle")}>
                      {recommendation.ranked.map((row) => (
                        <li key={row.supplier_id}>
                          <strong>{row.supplier_name}</strong> · <bdi dir="ltr">{row.unit_cost} {recommendation.currency}</bdi>
                          {row.rank > 1 ? <> · <bdi dir="ltr">+{row.delta_vs_best}</bdi></> : null}
                          {" · "}{t(`supplierSetup.sources.${row.source_type}`, { defaultValue: row.source_type })} · {row.is_stale ? <mark>{t("supplierSetup.ageDays", { days: row.age_days })}</mark> : t("supplierSetup.ageDays", { days: row.age_days })}
                          {" — "}<span className="muted">{t(`supplierSetup.why.${row.explanation}`)}</span>
                          {setup.preferred_supplier_id !== row.supplier_id ? <> <button className="text-button" disabled={busy} onClick={() => setPreferred(row.supplier_id, overrideReason)} type="button">{t("supplierSetup.chooseSupplier")}</button></> : null}
                        </li>
                      ))}
                    </ol>
                  ) : null}
                  {recommendation.excluded.length > 0 ? (
                    <p className="muted">{t("supplierSetup.notRanked")}: {recommendation.excluded.map((row) => `${row.supplier_name} (${t(`supplierSetup.excluded.${row.reason}`)}${row.detail ? ` ${row.detail}` : ""})`).join(", ")}</p>
                  ) : null}
                  <label className="field field-wide"><span>{t("supplierSetup.overrideReason")}</span><input maxLength={300} value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} /></label>
                </div>
              ) : null}
              {insights && insights.insights.length > 0 ? (
                <div className="price-insights">
                  <h5>{t("supplierSetup.insightsTitle")}</h5>
                  <p className="muted">{t("supplierSetup.insightsBody", { days: insights.stale_after_days })}</p>
                  <div aria-label={t("supplierSetup.insightsTitle")} className="table-region" role="region" tabIndex={0}>
                    <table className="cost-history" aria-label={t("supplierSetup.insightsTitle")}>
                      <thead><tr><th>{t("supplierSetup.supplier")}</th><th>{t("supplierSetup.comparable")}</th><th>{t("supplierSetup.latest")}</th><th>{t("supplierSetup.lowHigh")}</th><th>{t("supplierSetup.lastPurchase")}</th><th>{t("supplierSetup.trend")}</th><th>{t("supplierSetup.stability")}</th></tr></thead>
                      <tbody>
                        {insights.insights.map((row) => (
                          <tr key={`${row.supplier_id}-${row.cost_basis}-${row.pieces_per_box ?? 0}`}>
                            <td>{row.supplier_name}{row.is_preferred ? ` · ${t("invoiceEditor.preferred")}` : ""}</td>
                            <td>{row.currency} · {row.cost_basis}{row.pieces_per_box ? ` ×${row.pieces_per_box}` : ""}</td>
                            <td dir="ltr">{row.latest_unit_cost} <small>{t(`supplierSetup.sources.${row.latest_source_type}`, { defaultValue: row.latest_source_type })} · {row.age_days >= insights.stale_after_days ? <mark>{t("supplierSetup.ageDays", { days: row.age_days })}</mark> : t("supplierSetup.ageDays", { days: row.age_days })}</small></td>
                            <td dir="ltr">{row.lowest_unit_cost} – {row.highest_unit_cost}</td>
                            <td>{row.last_purchase_at ? <><bdi dir="ltr">{row.last_purchase_unit_cost}</bdi> · <time dateTime={row.last_purchase_at}>{new Date(row.last_purchase_at).toLocaleDateString()}</time></> : t("supplierSetup.noPurchaseYet")}</td>
                            <td dir="ltr">{row.recent_unit_costs.join(" ← ")}</td>
                            <td>{t(`supplierSetup.stabilityLabels.${row.stability}`)}{row.variation_percent ? ` (${row.variation_percent}%)` : ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </>
          ) : null}
        </article>
      </div>
      <PurchasePanel membershipId={membershipId} suppliers={suppliers} tenantId={tenantId} />
      <SupplierLedgerPanel tenantId={tenantId} suppliers={suppliers} />
    </section>
  );
}

function ProfileFields({ draft, idPrefix, onChange }: { draft: SupplierProfileDraft; idPrefix: string; onChange: (draft: SupplierProfileDraft) => void }) {
  const { t } = useTranslation();
  const set = (key: keyof SupplierProfileDraft) => (event: { target: { value: string } }) => onChange({ ...draft, [key]: event.target.value });
  return (
    <>
      <label className="field" htmlFor={`${idPrefix}-name`}><span>{t("supplierSetup.supplierName")}</span><input id={`${idPrefix}-name`} maxLength={200} required value={draft.name} onChange={set("name")} /></label>
      <label className="field" htmlFor={`${idPrefix}-contact`}><span>{t("supplierSetup.contactName")}</span><input id={`${idPrefix}-contact`} maxLength={200} value={draft.contact_name} onChange={set("contact_name")} /></label>
      <label className="field" htmlFor={`${idPrefix}-phone`}><span>{t("supplierSetup.contactPhone")}</span><input dir="ltr" id={`${idPrefix}-phone`} inputMode="tel" maxLength={64} value={draft.contact_phone} onChange={set("contact_phone")} /></label>
      <label className="field field-wide" htmlFor={`${idPrefix}-address`}><span>{t("supplierSetup.address")}</span><input id={`${idPrefix}-address`} maxLength={500} value={draft.address} onChange={set("address")} /></label>
      <label className="field" htmlFor={`${idPrefix}-lat`}><span>{t("supplierSetup.latitude")}</span><input dir="ltr" id={`${idPrefix}-lat`} inputMode="decimal" max="90" min="-90" step="0.000001" type="number" value={draft.latitude} onChange={set("latitude")} /></label>
      <label className="field" htmlFor={`${idPrefix}-lng`}><span>{t("supplierSetup.longitude")}</span><input dir="ltr" id={`${idPrefix}-lng`} inputMode="decimal" max="180" min="-180" step="0.000001" type="number" value={draft.longitude} onChange={set("longitude")} /></label>
      <label className="field field-wide" htmlFor={`${idPrefix}-notes`}><span>{t("supplierSetup.notes")}</span><input id={`${idPrefix}-notes`} maxLength={1000} value={draft.notes} onChange={set("notes")} /></label>
    </>
  );
}
