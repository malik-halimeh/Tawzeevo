import { money } from "../../utils/money";
import { type ReactNode, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Category, TenantProduct } from "../../api/types";
import { Icon } from "../Icon";
import { ChipRow } from "../listKit/ChipRow";
import { EmptyHint } from "../listKit/EmptyHint";
import { Fab } from "../listKit/Fab";
import { FilterSheet } from "../listKit/FilterSheet";
import { ListHeader } from "../listKit/ListHeader";
import { ListRow } from "../listKit/ListRow";

export type PublicationFilter = "all" | "published" | "hidden";

function ProductRow({ product, photo, management, onEdit, onTogglePublication, onBarcode }: {
  product: TenantProduct;
  photo: ReactNode;
  management: ReactNode;
  onEdit: () => void;
  onTogglePublication: () => void;
  onBarcode: () => void;
}) {
  const { t, i18n } = useTranslation();
  const manage = useRef<HTMLDetailsElement>(null);
  function openManagement(barcode: boolean) {
    if (barcode) onBarcode();
    if (manage.current) manage.current.open = true;
    // ActionMenu returns focus to its trigger first; then move to the selected controls.
    requestAnimationFrame(() => {
      const target = manage.current?.querySelector<HTMLElement>(barcode ? ".barcode-form input" : ".product-management select");
      target?.focus();
      target?.scrollIntoView?.({ block: "nearest" });
    });
  }
  return (
    <article className="product-list-item" data-product-id={product.id}>
      <ul className="list-rows">
        <ListRow
          actions={[
            { label: t("common.edit"), onSelect: onEdit },
            { label: t(product.is_published ? "tenantWorkspace.hide" : "tenantWorkspace.publish"), onSelect: onTogglePublication },
            { label: t("tenantWorkspace.addBarcode"), onSelect: () => openManagement(true) },
            { label: t("productsPage.pricingPhotos"), onSelect: () => openManagement(false) },
          ]}
          amount={<>{money(product.unit_price, product.currency)} / {product.price_basis}</>}
          onOpen={onEdit}
          subline={<>{photo}{i18n.resolvedLanguage === "ar" && product.name_ar ? <span className="product-arabic-name" dir="rtl" lang="ar">{product.name_ar}</span> : null}<span className={`status-badge ${product.is_published ? "status-current" : "status-closed"}`}>{t(product.is_published ? "tenantWorkspace.published" : "tenantWorkspace.hidden")}</span></>}
          title={product.name}
        />
      </ul>
      <details className="product-manage" ref={manage}>
        <summary>{t("common.manage")}</summary>
        {management}
      </details>
    </article>
  );
}

/** Presentation over the workspace's loaded products and unchanged mutation handlers. */
export function ProductsList({ products, hasProducts, categories, query, category, publication, onQuery, onCategory, onPublication, onAdd, onEdit, onTogglePublication, onBarcode, renderPhoto, renderManagement, children }: {
  products: TenantProduct[];
  hasProducts: boolean;
  categories: Category[];
  query: string;
  category: string;
  publication: PublicationFilter;
  onQuery: (value: string) => void;
  onCategory: (value: string) => void;
  onPublication: (value: PublicationFilter) => void;
  onAdd: () => void;
  onEdit: (product: TenantProduct) => void;
  onTogglePublication: (product: TenantProduct) => void;
  onBarcode: (product: TenantProduct) => void;
  renderPhoto: (product: TenantProduct) => ReactNode;
  renderManagement: (product: TenantProduct) => ReactNode;
  children: ReactNode;
}) {
  const { t, i18n } = useTranslation();
  const [draftCategory, setDraftCategory] = useState(category);
  const [draftPublication, setDraftPublication] = useState(publication);
  const [searchReset, setSearchReset] = useState(0);
  function clearFilters() {
    onQuery("");
    onCategory("");
    onPublication("all");
    setDraftCategory("");
    setDraftPublication("all");
    // ListHeader owns its search text; remount only on an explicit reset.
    setSearchReset((value) => value + 1);
  }
  return (
    <div className="products-page-list">
      <ListHeader
        actions={<button className="button products-add-button" onClick={onAdd} type="button"><Icon name="plus" small />{t("tenantWorkspace.addProduct")}</button>}
        count={products.length}
        countKey="productsPage.count"
        defaultSearch={query}
        key={searchReset}
        onSearch={onQuery}
        searchLabel={t("tenantWorkspace.productSearch")}
        title={t("tenantWorkspace.products")}
      />
      <ChipRow chips={[{ value: "", label: t("common.all") }, ...categories.filter((item) => item.is_active).map((item) => ({ value: item.id, label: i18n.resolvedLanguage === "ar" ? item.name_ar : item.name_en }))]} label={t("tenantWorkspace.category")} onChange={(value) => { onCategory(value); setDraftCategory(value); }} value={category} />
      <div>
        <FilterSheet activeCount={Number(Boolean(category)) + Number(publication !== "all")} onApply={() => { onCategory(draftCategory); onPublication(draftPublication); }} onClear={clearFilters} onClose={() => { setDraftCategory(category); setDraftPublication(publication); }}>
          <label className="field"><span>{t("tenantWorkspace.category")}</span><select onChange={(event) => setDraftCategory(event.target.value)} value={draftCategory}><option value="">{t("tenantWorkspace.allCategories")}</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name_en} / {item.name_ar}</option>)}</select></label>
          <label className="field"><span>{t("productsPage.visibility")}</span><select onChange={(event) => setDraftPublication(event.target.value as PublicationFilter)} value={draftPublication}><option value="all">{t("common.all")}</option><option value="published">{t("tenantWorkspace.published")}</option><option value="hidden">{t("tenantWorkspace.hidden")}</option></select></label>
        </FilterSheet>
      </div>
      {children}
      {hasProducts && !products.length ? <EmptyHint action={{ label: t("productsPage.clearFilters"), onSelect: clearFilters }} text={t("tenantWorkspace.noProductMatch")} /> : null}
      <div className="products-rows">
        {products.map((product) => <ProductRow key={product.id} management={renderManagement(product)} onBarcode={() => onBarcode(product)} onEdit={() => onEdit(product)} onTogglePublication={() => onTogglePublication(product)} photo={renderPhoto(product)} product={product} />)}
      </div>
      <Fab label={t("tenantWorkspace.addProduct")} onSelect={onAdd} />
    </div>
  );
}
