import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ProductPriceBasis } from "../../api/types";
import type { Supplier } from "../SupplierSetup";
import { InvoiceLineImage } from "./InvoiceLineImage";
import { lineNeedsMore, money, quantityValue, type EditorLine } from "./editorLine";

/**
 * A compact row opens the complete editor in place. Its "More" opens by itself for existing
 * adjustments; the parent owns which single row is expanded.
 * Every field stays mounted while folded, so nothing typed is lost and the save sends the same line.
 */
export function InvoiceLineCard({ line, index, lineTotal, totalCurrency, suppliers, onChange, onBasisChange, onRemove, onOpenSupplierSetup, expanded, onToggle, highlighted }: {
  expanded: boolean;
  onToggle: () => void;
  highlighted: string | undefined;
  line: EditorLine;
  index: number;
  /** The server's figure for this line (calculated or saved), when it matches the line as it stands. */
  lineTotal: string | undefined;
  totalCurrency: string;
  suppliers: Supplier[];
  onChange: (changes: Partial<EditorLine>) => void;
  onBasisChange: (basis: ProductPriceBasis) => void;
  onRemove: () => void;
  onOpenSupplierSetup?: ((productId?: string) => void) | undefined;
}) {
  const { t } = useTranslation();
  const moreId = useId();
  const controlsId = useId();
  const article = useRef<HTMLElement>(null);
  const quantity = quantityValue(line.quantity);
  const costMissing = (line.productId ? !line.costOptions.some((option) => option.unit_cost !== null) : suppliers.length === 0) && !line.costOverride;
  useEffect(() => {
    if (!highlighted || !article.current) return;
    const rect = article.current.getBoundingClientRect();
    const viewport = window.visualViewport;
    const top = viewport?.offsetTop ?? 0;
    const bottom = top + (viewport?.height ?? window.innerHeight);
    const bar = article.current.closest(".invoice-editor")?.querySelector(".invoice-action-bar");
    const barTop = bar?.getBoundingClientRect().top;
    const visibleBottom = barTop && barTop > top ? Math.min(bottom, barTop) : bottom;
    if (rect.top < top || rect.bottom > visibleBottom) article.current.scrollIntoView?.({ block: "nearest", behavior: "instant" });
  }, [highlighted]);
  const needsMore = lineNeedsMore(line);
  const [open, setOpen] = useState(needsMore);
  useEffect(() => {
    if (needsMore) setOpen(true);
  }, [needsMore]);

  return (
    <article className={`invoice-line${highlighted ? " is-new-line" : ""}`} ref={article}>
      <div className="line-compact">
        <button aria-controls={controlsId} aria-expanded={expanded} aria-label={t("invoiceEditorLayout.editLine", { number: index + 1, name: line.name })} className="line-expand" onClick={onToggle} type="button">
          <span className="line-compact-name">{line.imageUrl ? <InvoiceLineImage name={line.name} url={line.imageUrl} /> : null}<strong>{line.name}</strong>{needsMore || costMissing ? <span className="line-marker" title={t("invoiceEditorLayout.lineDetails")} aria-label={t("invoiceEditorLayout.lineDetails")}>•</span> : null}</span>
          <span className="line-unit-price"><bdi dir="ltr">× {money(line.unitPrice ?? line.manualUnitPrice ?? "—", totalCurrency)}</bdi> {t(line.basis === "BOX" ? "tenantWorkspace.box" : "tenantWorkspace.piece")}</span>
          <bdi className="line-compact-total" dir="ltr">{lineTotal === undefined ? "—" : money(lineTotal, totalCurrency)}</bdi>
        </button>
        <div className="line-stepper" role="group" aria-label={t("invoiceEditorLayout.lineQuantity", { name: line.name })}>
          <button aria-label={t("invoiceEditorLayout.decreaseQuantity", { name: line.name })} disabled={quantity === undefined || quantity <= 1} onClick={() => onChange({ quantity: String(Number((quantity! - 1).toFixed(4))) })} type="button">−</button>
          <bdi dir="ltr">{quantity ?? "—"}</bdi>
          <button aria-label={t("invoiceEditorLayout.increaseQuantity", { name: line.name })} disabled={quantity === undefined} onClick={() => onChange({ quantity: String(Number((quantity! + 1).toFixed(4))) })} type="button">+</button>
        </div>
      </div>
      <div className="line-expanded" hidden={!expanded} id={controlsId}>
      <code dir="ltr">{line.barcode ?? t("invoiceEditor.manual")}</code>
      <div className="line-fields line-essentials">
        <label className="field"><span>{t("invoiceEditor.quantityExpression")}</span><input dir="ltr" value={line.quantity} onChange={(event) => onChange({ quantity: event.target.value })} /></label>
        <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span><select value={line.basis} onChange={(event) => onBasisChange(event.target.value as ProductPriceBasis)}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
        <p className="line-total"><span>{t("invoiceEditorLayout.lineTotal")}</span><bdi dir="ltr">{lineTotal === undefined ? "—" : money(lineTotal, totalCurrency)}</bdi></p>
      </div>
      {/* The spoken name starts with the visible words and adds which line it belongs to. */}
      <button aria-controls={moreId} aria-expanded={open} aria-label={`${t("invoiceEditorLayout.lineMore")} ${t("invoiceEditorLayout.lineMoreOf", { name: line.name })}`} className="text-button line-more-toggle" onClick={() => setOpen((current) => !current)} type="button">
        {t("invoiceEditorLayout.lineMore")}
      </button>
      <div className="line-more" hidden={!open} id={moreId}>
        <div className="line-fields">
          <label className="field"><span>{t("invoiceEditor.lineDiscount")}</span><input dir="ltr" value={line.lineDiscount} onChange={(event) => onChange({ lineDiscount: event.target.value })} /></label>
          <label className="field"><span>{t("invoiceEditor.lineMarkup")}</span><input dir="ltr" value={line.lineMarkup} onChange={(event) => onChange({ lineMarkup: event.target.value })} /></label>
        </div>
        {line.costOptions.length ? <div className="line-cost-controls"><label className="field"><span>{t("invoiceEditor.supplierCost")}</span><select value={line.supplierId ?? ""} onChange={(event) => onChange({ supplierId: event.target.value, supplierTouched: true })}><option value="">—</option>{line.costOptions.map((option) => <option dir="ltr" key={option.supplier_id} value={option.supplier_id}>{option.supplier_name} · {money(option.unit_cost ?? "—", option.currency)}{option.is_preferred ? ` · ${t("invoiceEditor.preferred")}` : ""}</option>)}</select></label><label className="field"><span>{t("invoiceEditor.costOverride")}</span><input dir="ltr" min="0" step="0.0001" type="number" value={line.costOverride} onChange={(event) => onChange({ costOverride: event.target.value })} /></label>{line.costOverride ? <label className="field field-wide"><span>{t("invoiceEditor.overrideReason")}</span><input required value={line.costOverrideReason} onChange={(event) => onChange({ costOverrideReason: event.target.value })} /></label> : null}</div> : null}
        {!line.productId && suppliers.length ? <div className="line-cost-controls"><label className="field"><span>{t("invoiceEditor.manualLineCost")}</span><select value={line.supplierId ?? ""} onChange={(event) => onChange({ supplierId: event.target.value || undefined, supplierTouched: true })}><option value="">—</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label><label className="field"><span>{t("invoiceEditor.costOverride")}</span><input dir="ltr" min="0" step="0.0001" type="number" value={line.costOverride} onChange={(event) => onChange({ costOverride: event.target.value })} /></label>{line.costOverride ? <label className="field field-wide"><span>{t("invoiceEditor.overrideReason")}</span><input required value={line.costOverrideReason} onChange={(event) => onChange({ costOverrideReason: event.target.value })} /></label> : null}</div> : null}
      </div>
      {costMissing ? <p className="cost-missing" role="note">{t("invoiceEditor.costMissing")}{onOpenSupplierSetup ? <> <button className="text-button" onClick={() => onOpenSupplierSetup(line.productId)} type="button">{t("invoiceEditor.openSupplierSetup")}</button></> : null}</p> : null}
      <button className="text-button danger-link remove-line" onClick={onRemove} type="button">{t("common.remove")}</button>
      </div>
    </article>
  );
}
