import { FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis, TenantProduct, TenantProductListResponse } from "../api/types";
import { ErrorState } from "./Ui";

export interface Supplier {
  id: string;
  tenant_id: string;
  name: string;
  created_at: string;
  updated_at: string;
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
export function SupplierSetup({ tenantId, initialProductId }: { tenantId: string; initialProductId?: string }) {
  const { t } = useTranslation();
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<TenantProduct[]>([]);
  const [supplierName, setSupplierName] = useState("");
  const [renaming, setRenaming] = useState<{ id: string; name: string }>();
  const [productId, setProductId] = useState(initialProductId ?? "");
  const [setup, setSetup] = useState<ProductCostSetup>();
  const [costSupplierId, setCostSupplierId] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [basis, setBasis] = useState<ProductPriceBasis>("PIECE");
  const [piecesPerBox, setPiecesPerBox] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

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

  const loadSetup = useCallback(async (id: string) => {
    if (!id) { setSetup(undefined); return; }
    setSetup(await apiRequest<ProductCostSetup>(`/api/v1/suppliers/products/${id}/costs?tenant_id=${tenantId}`));
  }, [tenantId]);

  useEffect(() => { void run(async () => { await Promise.all([loadSuppliers(), loadProducts()]); }); }, [run, loadSuppliers, loadProducts]);
  useEffect(() => { void run(() => loadSetup(productId)); }, [run, loadSetup, productId]);

  const product = products.find((item) => item.id === productId);

  const createSupplier = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      await apiRequest<Supplier>(`/api/v1/suppliers?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ name: supplierName }) });
      setSupplierName("");
      await loadSuppliers();
      setNotice(t("supplierSetup.supplierCreated"));
    });
  };

  const saveRename = (event: FormEvent) => {
    event.preventDefault();
    if (!renaming) return;
    void run(async () => {
      await apiRequest<Supplier>(`/api/v1/suppliers/${renaming.id}?tenant_id=${tenantId}`, { method: "PATCH", body: JSON.stringify({ name: renaming.name }) });
      setRenaming(undefined);
      await loadSuppliers();
      setNotice(t("supplierSetup.supplierRenamed"));
    });
  };

  const appendCost = (event: FormEvent) => {
    event.preventDefault();
    if (!product) return;
    void run(async () => {
      const response = await apiRequest<ProductCostSetup>(`/api/v1/suppliers/products/${product.id}/costs?tenant_id=${tenantId}`, {
        method: "POST",
        body: JSON.stringify({
          supplier_id: costSupplierId,
          unit_cost: unitCost,
          currency: product.currency,
          cost_basis: basis,
          pieces_per_box: piecesPerBox ? Number(piecesPerBox) : null,
          notes: notes || null,
        }),
      });
      setSetup(response);
      setUnitCost(""); setNotes("");
      setNotice(t("supplierSetup.costAppended"));
    });
  };

  const setPreferred = (supplierId: string | null) => {
    if (!product) return;
    void run(async () => {
      setSetup(await apiRequest<ProductCostSetup>(`/api/v1/suppliers/products/${product.id}/preferred-supplier?tenant_id=${tenantId}`, {
        method: "PUT",
        body: JSON.stringify({ supplier_id: supplierId }),
      }));
      setNotice(t("supplierSetup.preferredSaved"));
    });
  };

  const supplierName_ = (id: string) => suppliers.find((supplier) => supplier.id === id)?.name ?? "—";

  return (
    <section className="supplier-setup" aria-labelledby="supplier-setup-title">
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
          <form className="inline-form" onSubmit={createSupplier}>
            <label className="field"><span>{t("supplierSetup.supplierName")}</span><input required value={supplierName} onChange={(event) => setSupplierName(event.target.value)} /></label>
            <button className="button" disabled={busy} type="submit">{t("supplierSetup.addSupplier")}</button>
          </form>
          {suppliers.length === 0 ? <p className="empty-note">{t("supplierSetup.noSuppliers")}</p> : (
            <ul className="supplier-list">
              {suppliers.map((supplier) => (
                <li key={supplier.id}>
                  {renaming?.id === supplier.id ? (
                    <form className="inline-form" onSubmit={saveRename}>
                      <label className="field"><span>{t("supplierSetup.supplierName")}</span><input required value={renaming.name} onChange={(event) => setRenaming({ id: supplier.id, name: event.target.value })} /></label>
                      <button className="button" disabled={busy} type="submit">{t("common.saveChanges")}</button>
                      <button className="text-button" onClick={() => setRenaming(undefined)} type="button">{t("common.cancel")}</button>
                    </form>
                  ) : (
                    <><span>{supplier.name}</span><button className="text-button" disabled={busy} onClick={() => setRenaming({ id: supplier.id, name: supplier.name })} type="button">{t("supplierSetup.rename")}</button></>
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
                <label className="field field-wide"><span>{t("supplierSetup.notes")}</span><input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
                <button className="button" disabled={busy || suppliers.length === 0} type="submit">{t("supplierSetup.appendCost")}</button>
              </form>
              {suppliers.length === 0 ? <p className="empty-note">{t("supplierSetup.createSupplierFirst")}</p> : null}
              {setup.entries.length === 0 ? <p className="empty-note">{t("supplierSetup.noCosts")}</p> : (
                <table className="cost-history">
                  <thead><tr><th>{t("supplierSetup.supplier")}</th><th>{t("supplierSetup.unitCost")}</th><th>{t("tenantWorkspace.priceBasis")}</th><th>{t("supplierSetup.effectiveAt")}</th><th>{t("supplierSetup.source")}</th><th /></tr></thead>
                  <tbody>
                    {setup.entries.map((entry) => (
                      <tr key={entry.id}>
                        <td>{supplierName_(entry.supplier_id)}{setup.preferred_supplier_id === entry.supplier_id ? ` · ${t("invoiceEditor.preferred")}` : ""}</td>
                        <td dir="ltr">{entry.unit_cost} {entry.currency}</td>
                        <td>{entry.cost_basis}{entry.pieces_per_box ? ` ×${entry.pieces_per_box}` : ""}</td>
                        <td><time dateTime={entry.effective_at}>{new Date(entry.effective_at).toLocaleString()}</time></td>
                        <td>{entry.source_type}</td>
                        <td>{setup.preferred_supplier_id !== entry.supplier_id ? <button className="text-button" disabled={busy} onClick={() => setPreferred(entry.supplier_id)} type="button">{t("supplierSetup.makePreferred")}</button> : null}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {setup.preferred_supplier_id ? <button className="text-button" disabled={busy} onClick={() => setPreferred(null)} type="button">{t("supplierSetup.clearPreferred")}</button> : null}
            </>
          ) : null}
        </article>
      </div>
    </section>
  );
}
