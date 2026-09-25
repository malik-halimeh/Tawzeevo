import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiBlobRequest, apiRequest } from "../api/client";
import type {
  BarcodeLookupResponse,
  BarcodePackageLevel,
  Category,
  CategoryListResponse,
  Customer,
  CustomerGrade,
  CustomerSearchResponse,
  GradeDiscount,
  GradeDiscountListResponse,
  ProductGradePrice,
  ProductImage,
  TenantContext,
  TenantProduct,
  TenantProductListResponse,
} from "../api/types";
import { ErrorState, LoadingState, StatusBadge, SuccessNotice } from "./Ui";
import { CopilotPanel } from "./CopilotPanel";
import { AttentionList, CustomerSignals, TodayBrief } from "./IntelligencePanel";
import { InvoiceEditor } from "./InvoiceEditor";
import { SupplierSetup } from "./SupplierSetup";
import { CONNECT_RESULT_KEY } from "../backup/connect";
import { isOfflineFailure } from "../offline/network";
import { createCustomerOffline, createProductOffline, updateCustomerOffline, updateProductOffline } from "../offline/outbox";
import { AnalyticsPanel } from "./AnalyticsPanel";
import { BackupPanel } from "./BackupPanel";
import { BrandingPanel } from "./BrandingPanel";
import { CampaignPanel } from "./CampaignPanel";
import { CustomerLinkControls } from "./CustomerLinkControls";
import { DeliveryPanel } from "./DeliveryPanel";
import { Arrow, Icon } from "./Icon";
import { MyWorkPanel } from "./MyWorkPanel";
import { OrdersPanel } from "./OrdersPanel";
import { PickupPanel } from "./PickupPanel";
import { ProcurementPanel } from "./ProcurementPanel";
import { StorefrontSettings } from "./StorefrontSettings";
import { SyncPanel } from "./SyncPanel";
import { SYNC_ANCHOR, type WorkspaceSection, sectionFromSearch, sectionHref, selectedContext, tenantFromSearch, workspaceSearch } from "./workspaceSections";

const grades: CustomerGrade[] = ["A+", "A", "B+", "B"];

interface CustomerDraft {
  name: string;
  phone: string;
  address: string;
  latitude: string;
  longitude: string;
  grade: "" | CustomerGrade;
}

const emptyCustomer: CustomerDraft = {
  name: "",
  phone: "",
  address: "",
  latitude: "",
  longitude: "",
  grade: "",
};

interface CategoryDraft {
  name_en: string;
  name_ar: string;
  slug: string;
  display_order: string;
}

const emptyCategory: CategoryDraft = {
  name_en: "",
  name_ar: "",
  slug: "",
  display_order: "0",
};

interface ProductDraft {
  category_id: string;
  master_product_id: string | null;
  name: string;
  name_ar: string;
  barcode: string;
  barcode_package_level: BarcodePackageLevel;
  unit_price: string;
  currency: string;
  price_basis: BarcodePackageLevel;
  pieces_per_box: string;
  is_published: boolean;
}

const emptyProduct: ProductDraft = {
  category_id: "",
  master_product_id: null,
  name: "",
  name_ar: "",
  barcode: "",
  barcode_package_level: "PIECE",
  unit_price: "",
  currency: "USD",
  price_basis: "PIECE",
  pieces_per_box: "",
  is_published: false,
};

function optional(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

const emptyDiscounts: Record<CustomerGrade, string> = {
  "A+": "",
  A: "",
  "B+": "",
  B: "",
};

function AuthenticatedProductImage({ image }: { image: ProductImage }) {
  const { t } = useTranslation();
  const [source, setSource] = useState<string>();

  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    void apiBlobRequest(image.url)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => {
        if (active) setSource(undefined);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [image.url]);

  return source ? (
    <img
      alt={image.alt_text ?? t("tenantWorkspace.productImageFallback")}
      className="product-image"
      src={source}
    />
  ) : (
    <span className="product-image-placeholder">{t("common.loading")}</span>
  );
}

function GradeDiscountEditor({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<CustomerGrade, string>>(emptyDiscounts);
  const [busyGrade, setBusyGrade] = useState<CustomerGrade>();
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const discounts = useQuery({
    queryKey: ["tenant-grade-discounts", tenantId],
    queryFn: () =>
      apiRequest<GradeDiscountListResponse>(`/api/v1/tenants/${tenantId}/grade-discounts`),
  });

  useEffect(() => {
    if (!discounts.data) return;
    const next = { ...emptyDiscounts };
    for (const discount of discounts.data.discounts) {
      next[discount.grade] = discount.discount_percent;
    }
    setDrafts(next);
  }, [discounts.data]);

  const save = (event: FormEvent, grade: CustomerGrade) => {
    event.preventDefault();
    const value = drafts[grade].trim();
    setBusyGrade(grade);
    setError(undefined);
    setSaved(false);
    void (value
      ? apiRequest<GradeDiscount>(
          `/api/v1/tenants/${tenantId}/grade-discounts/${encodeURIComponent(grade)}`,
          { method: "PUT", body: JSON.stringify({ discount_percent: value }) },
        )
      : apiRequest<void>(
          `/api/v1/tenants/${tenantId}/grade-discounts/${encodeURIComponent(grade)}`,
          { method: "DELETE" },
        )
    )
      .then(async () => {
        await queryClient.invalidateQueries({ queryKey: ["tenant-grade-discounts", tenantId] });
        setSaved(true);
      })
      .catch(setError)
      .finally(() => setBusyGrade(undefined));
  };

  return (
    <article className="content-card grade-pricing-card">
      <p className="section-kicker">{t("tenantWorkspace.gradePricing")}</p>
      <h3>{t("tenantWorkspace.defaultDiscounts")}</h3>
      <p>{t("tenantWorkspace.defaultDiscountsBody")}</p>
      {discounts.isLoading ? <LoadingState /> : null}
      {discounts.error ? <ErrorState error={discounts.error} /> : null}
      {error ? <ErrorState error={error} /> : null}
      {saved ? <SuccessNotice>{t("tenantWorkspace.discountSaved")}</SuccessNotice> : null}
      {!discounts.isLoading ? <div className="grade-discount-grid">
        {grades.map((grade) => (
          <form key={grade} onSubmit={(event) => save(event, grade)}>
            <label className="field">
              <span>{t("tenantWorkspace.gradeDiscountLabel", { grade })}</span>
              <input
                dir="ltr"
                max="100"
                min="0"
                placeholder="—"
                step="0.0001"
                type="number"
                value={drafts[grade]}
                onChange={(event) => setDrafts({ ...drafts, [grade]: event.target.value })}
              />
            </label>
            <button className="text-button" disabled={busyGrade === grade} type="submit">
              {t(drafts[grade] ? "common.saveChanges" : "tenantWorkspace.clearDiscount")}
            </button>
          </form>
        ))}
      </div> : null}
    </article>
  );
}

function ProductPricingMediaControls({
  product,
  tenantId,
}: {
  product: TenantProduct;
  tenantId: string;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [grade, setGrade] = useState<CustomerGrade>("A+");
  const [gradePrice, setGradePrice] = useState("");
  const [imageFile, setImageFile] = useState<File>();
  const [imageAlt, setImageAlt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const refreshProduct = () =>
    queryClient.invalidateQueries({ queryKey: ["tenant-products", tenantId] });

  const saveGradePrice = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    void apiRequest<ProductGradePrice>(
      `/api/v1/tenants/${tenantId}/products/${product.id}/grade-prices/${encodeURIComponent(grade)}`,
      { method: "PUT", body: JSON.stringify({ unit_price: gradePrice }) },
    )
      .then(async () => {
        await refreshProduct();
        setGradePrice("");
        setNotice(t("tenantWorkspace.gradePriceSaved"));
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  const clearGradePrice = () => {
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    void apiRequest<void>(
      `/api/v1/tenants/${tenantId}/products/${product.id}/grade-prices/${encodeURIComponent(grade)}`,
      { method: "DELETE" },
    )
      .then(async () => {
        await refreshProduct();
        setNotice(t("tenantWorkspace.gradePriceCleared"));
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  const uploadImage = (event: FormEvent) => {
    event.preventDefault();
    if (!imageFile) return;
    const body = new FormData();
    body.append("file", imageFile);
    if (imageAlt.trim()) body.append("alt_text", imageAlt.trim());
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    void apiRequest<ProductImage>(
      `/api/v1/tenants/${tenantId}/products/${product.id}/images`,
      { method: "POST", body },
    )
      .then(async () => {
        await refreshProduct();
        setImageFile(undefined);
        setImageAlt("");
        setNotice(t("tenantWorkspace.imageUploaded"));
      })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  return (
    <div className="product-management">
      <dl className="price-pair">
        <div><dt>{t("tenantWorkspace.piecePrice")}</dt><dd dir="ltr">{product.piece_price} {product.currency}</dd></div>
        <div><dt>{t("tenantWorkspace.boxPrice")}</dt><dd dir="ltr">{product.box_price ?? "—"} {product.currency}</dd></div>
      </dl>
      {product.images.length ? (
        <div className="product-image-strip">
          {product.images.map((image) => <AuthenticatedProductImage image={image} key={`${image.ownership}-${image.id}`} />)}
        </div>
      ) : null}
      {product.grade_prices.length ? (
        <div className="grade-price-chips">
          {product.grade_prices.map((price) => <span key={price.id}>{price.grade}: <bdi dir="ltr">{price.unit_price} {product.currency} / {product.price_basis}</bdi></span>)}
        </div>
      ) : null}
      {error ? <ErrorState error={error} /> : null}
      {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}
      <form className="inline-form compact-management-form" onSubmit={saveGradePrice}>
        <label className="field"><span>{t("tenantWorkspace.explicitGrade")}</span><select value={grade} onChange={(event) => setGrade(event.target.value as CustomerGrade)}>{grades.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="field"><span>{t("tenantWorkspace.explicitGradePrice")}</span><input dir="ltr" min="0" required step="0.0001" type="number" value={gradePrice} onChange={(event) => setGradePrice(event.target.value)} /></label>
        <button className="button" disabled={busy} type="submit">{t("tenantWorkspace.saveGradePrice")}</button>
        <button className="text-button danger-link" disabled={busy} onClick={clearGradePrice} type="button">{t("tenantWorkspace.clearGradePrice")}</button>
      </form>
      <form className="inline-form compact-management-form" onSubmit={uploadImage}>
        <label className="field"><span>{t("tenantWorkspace.productImage")}</span><input accept="image/jpeg,image/png,image/webp" required type="file" onChange={(event) => setImageFile(event.target.files?.[0])} /></label>
        <label className="field"><span>{t("tenantWorkspace.imageAlt")}</span><input maxLength={300} value={imageAlt} onChange={(event) => setImageAlt(event.target.value)} /></label>
        <button className="button" disabled={busy || !imageFile} type="submit">{t("tenantWorkspace.uploadImage")}</button>
      </form>
    </div>
  );
}

/** One pane below the 1100px list/detail layout, as on the work screen: an open record replaces the list. */
const ONE_PANE = "(max-width: 1099px)";
const singlePane = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(ONE_PANE).matches;

/** The workspace's result and error notices sit directly above the customer panes; this is the topmost one. */
function noticeAbove(node: Element | null): Element | undefined {
  let top: Element | undefined;
  let sibling = node?.previousElementSibling;
  while (sibling && sibling.classList.contains("notice")) {
    top = sibling;
    sibling = sibling.previousElementSibling;
  }
  return top;
}

/** Where focus goes once the customer panes have rendered the member's last step. */
type CustomerFocus =
  | { to: "detail" | "form" | "edit" | "saved" | "failed" }
  | { to: "list"; row: string | undefined; scrollY: number };

interface CustomerDirectoryProps {
  tenantId: string;
  busy: boolean;
  phoneSearch: string;
  setPhoneSearch: (value: string) => void;
  matches: Customer[];
  searchCustomers: (event: FormEvent) => void;
  customerDraft: CustomerDraft;
  setCustomerDraft: (draft: CustomerDraft) => void;
  editingCustomerId: string | undefined;
  setEditingCustomerId: (id: string | undefined) => void;
  saveCustomer: (event: FormEvent) => void;
  editCustomer: (customer: Customer) => void;
  linkCustomerId: string | undefined;
  setLinkCustomerId: (id: string | undefined) => void;
  /** A customer named in the address (`customer`), e.g. opened from a priority or an assistant answer. */
  focusCustomerId: string | null;
}

/**
 * Customers as a list and a record, like the work screen: the phone search and its results beside
 * the chosen customer from 1100px, one pane at a time below. Presentation only — the search, save
 * and edit handlers (with their offline paths), the notices and the storefront-link controls are the
 * workspace's own, passed in unchanged; this component keeps which pane is open and where focus goes.
 */
function CustomerDirectory({ tenantId, busy, phoneSearch, setPhoneSearch, matches, searchCustomers, customerDraft, setCustomerDraft, editingCustomerId, setEditingCustomerId, saveCustomer, editCustomer, linkCustomerId, setLinkCustomerId, focusCustomerId }: CustomerDirectoryProps) {
  const { t } = useTranslation();
  const [, setSearchParams] = useSearchParams();
  const handledFocus = useRef<string | null>(null);
  const [selectedId, setSelectedId] = useState(editingCustomerId);
  const [creating, setCreating] = useState(false);
  const [detailOpen, setDetailOpen] = useState(editingCustomerId !== undefined);
  const [, setFocusRequests] = useState(0);
  const root = useRef<HTMLElement>(null);
  const phoneInput = useRef<HTMLInputElement>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const formHeading = useRef<HTMLHeadingElement>(null);
  const editButton = useRef<HTMLButtonElement>(null);
  const saveButton = useRef<HTMLButtonElement>(null);
  const rows = useRef(new Map<string, HTMLButtonElement>());
  const listScroll = useRef(0);
  const pendingSave = useRef<Customer[] | undefined>(undefined);
  const pendingFocus = useRef<CustomerFocus | undefined>(undefined);
  const focusAfterRender = useCallback((next: CustomerFocus) => {
    pendingFocus.current = next;
    setFocusRequests((count) => count + 1);
  }, []);

  const formMode = editingCustomerId ? "edit" : creating ? "create" : undefined;
  const selected = matches.find((customer) => customer.id === selectedId);
  // The record the detail pane shows, marked in the list; none while a new customer is being added.
  const shownId = formMode === "edit" ? editingCustomerId : formMode ? undefined : selected?.id;
  const initial = (name: string) => name.trim().slice(0, 1).toUpperCase();

  // Focus and scrolling follow a step once its pane has rendered, before paint. Declared before the
  // save handling below, so a request made there is carried out after the render it causes.
  useLayoutEffect(() => {
    const next = pendingFocus.current;
    if (!next) return;
    pendingFocus.current = undefined;
    const onePane = singlePane();
    const bringIntoView = (node: Element | null | undefined, block: ScrollLogicalPosition) => {
      if (node && typeof node.scrollIntoView === "function") node.scrollIntoView({ block });
    };
    switch (next.to) {
      case "list": {
        // Back on the results: the same scroll position, with focus on the customer just viewed.
        if (onePane) window.scrollTo(0, next.scrollY);
        const target = (next.row ? rows.current.get(next.row) : undefined) ?? addButton.current;
        target?.focus(onePane ? { preventScroll: true } : undefined);
        // Moves only when the target is not fully visible (a saved record joins the end of the results);
        // its scroll margin keeps it clear of the bottom bar.
        if (onePane) bringIntoView(target, "nearest");
        return;
      }
      case "failed":
        // Save was disabled while sending, which can drop focus; the error itself is announced.
        if (!root.current?.contains(document.activeElement)) saveButton.current?.focus({ preventScroll: true });
        if (onePane) bringIntoView(noticeAbove(root.current), "nearest");
        return;
      case "edit":
        editButton.current?.focus();
        return;
      default: {
        const heading = next.to === "form" ? formHeading.current : detailHeading.current;
        heading?.focus(onePane ? { preventScroll: true } : undefined);
        if (!onePane) return;
        // On a phone the pane is shown from its top; after a save, from the result notice above it.
        const record = heading?.closest("article");
        bringIntoView(next.to === "saved" ? noticeAbove(root.current) ?? record : record, "start");
      }
    }
  });

  // A save the workspace completed (online, or queued on this device) adds the record to the results
  // and clears the form: the pane then shows that customer. A refused save keeps the form and its error.
  useLayoutEffect(() => {
    const before = pendingSave.current;
    if (!before || busy) return;
    pendingSave.current = undefined;
    if (matches === before) { focusAfterRender({ to: "failed" }); return; }
    const saved = matches[matches.length - 1];
    setCreating(false);
    setSelectedId(saved?.id);
    if (saved) { focusAfterRender({ to: "saved" }); return; }
    setDetailOpen(false);
    focusAfterRender({ to: "list", row: undefined, scrollY: listScroll.current });
  }, [busy, matches, focusAfterRender]);

  // A customer named in the address opens once it is among the results (the workspace loads it by id).
  useEffect(() => {
    if (!focusCustomerId || handledFocus.current === focusCustomerId || !matches.some((customer) => customer.id === focusCustomerId)) return;
    handledFocus.current = focusCustomerId;
    setEditingCustomerId(undefined);
    setCustomerDraft(emptyCustomer);
    setCreating(false);
    setSelectedId(focusCustomerId);
    setDetailOpen(true);
    if (singlePane()) focusAfterRender({ to: "detail" });
  }, [focusCustomerId, matches, setEditingCustomerId, setCustomerDraft, focusAfterRender]);
  // Leaving that record forgets the address's customer, so the same priority opens it again.
  const clearFocus = () => {
    if (!focusCustomerId) return;
    handledFocus.current = null;
    setSearchParams((current) => { const next = new URLSearchParams(current); next.delete("customer"); return next; }, { replace: true });
  };

  const rememberListScroll = () => { if (singlePane()) listScroll.current = window.scrollY; };
  const discardForm = () => { setEditingCustomerId(undefined); setCustomerDraft(emptyCustomer); setCreating(false); };
  // The results change beneath the search, so the phone field keeps the focus (Search is busy meanwhile).
  const submitSearch = (event: FormEvent) => {
    phoneInput.current?.focus();
    searchCustomers(event);
  };
  const openCustomer = (customer: Customer) => {
    if (formMode) discardForm();
    clearFocus();
    rememberListScroll();
    setSelectedId(customer.id);
    setDetailOpen(true);
    // On a phone the record replaces the list and focus moves to its name; beside the list it stays on the row.
    if (singlePane()) focusAfterRender({ to: "detail" });
  };
  const backToList = () => {
    clearFocus();
    setDetailOpen(false);
    focusAfterRender({ to: "list", row: selected?.id, scrollY: listScroll.current });
  };
  const addCustomer = () => {
    rememberListScroll();
    discardForm(); // an edit left open never leaks into a new customer
    setCreating(true);
    setDetailOpen(true);
    focusAfterRender({ to: "form" });
  };
  const editSelected = (customer: Customer) => {
    editCustomer(customer);
    setCreating(false);
    focusAfterRender({ to: "form" });
  };
  const cancelForm = () => {
    const backToRecord = formMode === "edit" && selected !== undefined;
    discardForm();
    if (backToRecord) { focusAfterRender({ to: "edit" }); return; }
    setDetailOpen(false);
    focusAfterRender({ to: "list", row: undefined, scrollY: listScroll.current });
  };
  const submitCustomer = (event: FormEvent) => {
    pendingSave.current = matches;
    saveCustomer(event);
  };

  return (
    <section aria-label={t("tenantWorkspace.customers")} className={`customers workspace${detailOpen && (formMode || selected) ? " show-detail" : ""}`} ref={root}>
      <div className="workspace-list">
        <article className="customer-search">
          <p className="section-kicker">{t("tenantWorkspace.phoneLookup")}</p>
          <h2>{t("tenantWorkspace.findCustomer")}</h2>
          <p className="muted">{t("tenantWorkspace.chooseCustomer")}</p>
          <form className="inline-form" onSubmit={submitSearch}>
            <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" inputMode="tel" ref={phoneInput} required value={phoneSearch} onChange={(event) => setPhoneSearch(event.target.value)} /></label>
            <button className="button button-secondary" disabled={busy} type="submit"><Icon name="search" small />{t("common.search")}</button>
          </form>
          <button className="button customer-add" onClick={addCustomer} ref={addButton} type="button"><Icon name="plus" small />{t("tenantWorkspace.addCustomer")}</button>
        </article>
        {matches.length ? (
          <ul aria-label={t("tenantWorkspace.matchList")} className="stop-list customer-list">
            {matches.map((customer) => (
              <li className="stop-item" key={customer.id}>
                <button aria-current={shownId === customer.id ? "true" : undefined} className={`stop-button customer-row${shownId === customer.id ? " selected" : ""}`} onClick={() => openCustomer(customer)} ref={(node) => { if (node) rows.current.set(customer.id, node); else rows.current.delete(customer.id); }} type="button">
                  <span className="avatar" aria-hidden="true">{initial(customer.name)}</span>
                  <span className="stop-copy"><strong>{customer.name}</strong><small><bdi dir="ltr">{customer.phone}</bdi></small>{customer.address ? <small>{customer.address}</small> : null}</span>
                  {customer.grade ? <span className="badge">{t("tenantWorkspace.grade")} <bdi>{customer.grade}</bdi></span> : null}
                  <Arrow />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <AttentionList tenantId={tenantId} />
      </div>
      {formMode ? (
        <article aria-labelledby="customer-form-title" className="detail customer-detail">
          <div className="detail-inner">
            <p className="section-kicker">{formMode === "edit" ? t("common.edit") : t("tenantWorkspace.newStop")}</p>
            <h2 className="customer-form-title" id="customer-form-title" ref={formHeading} tabIndex={-1}>{formMode === "edit" ? t("tenantWorkspace.editCustomer") : t("tenantWorkspace.addCustomer")}</h2>
            <form className="form-grid" onSubmit={submitCustomer}>
              <label className="field"><span>{t("tenantWorkspace.customerName")}</span><input required value={customerDraft.name} onChange={(event) => setCustomerDraft({ ...customerDraft, name: event.target.value })} /></label>
              <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" inputMode="tel" required value={customerDraft.phone} onChange={(event) => setCustomerDraft({ ...customerDraft, phone: event.target.value })} /></label>
              <label className="field field-wide"><span>{t("tenantWorkspace.address")}</span><input value={customerDraft.address} onChange={(event) => setCustomerDraft({ ...customerDraft, address: event.target.value })} /></label>
              <label className="field"><span>{t("tenantWorkspace.latitude")}</span><input dir="ltr" inputMode="decimal" value={customerDraft.latitude} onChange={(event) => setCustomerDraft({ ...customerDraft, latitude: event.target.value })} /></label>
              <label className="field"><span>{t("tenantWorkspace.longitude")}</span><input dir="ltr" inputMode="decimal" value={customerDraft.longitude} onChange={(event) => setCustomerDraft({ ...customerDraft, longitude: event.target.value })} /></label>
              <label className="field"><span>{t("tenantWorkspace.grade")}</span><select value={customerDraft.grade} onChange={(event) => setCustomerDraft({ ...customerDraft, grade: event.target.value as CustomerDraft["grade"] })}><option value="">{t("tenantWorkspace.noGrade")}</option>{grades.map((grade) => <option key={grade}>{grade}</option>)}</select></label>
              <div className="form-actions field-wide"><button className="button" disabled={busy} ref={saveButton} type="submit">{busy ? t("common.saving") : t("common.saveChanges")}</button><button className="button button-secondary" onClick={cancelForm} type="button">{t("common.cancel")}</button></div>
            </form>
          </div>
        </article>
      ) : selected ? (
        <article aria-labelledby="customer-detail-title" className="detail customer-detail">
          <div className="detail-inner">
            <button className="text-btn mobile-back" onClick={backToList} type="button"><Arrow back />{t("tenantWorkspace.allCustomers")}</button>
            <div className="customer-identity">
              <span className="avatar" aria-hidden="true">{initial(selected.name)}</span>
              <h2 className="detail-name" id="customer-detail-title" ref={detailHeading} tabIndex={-1}>{selected.name}</h2>
            </div>
            <dl className="customer-facts">
              <div><dt>{t("fields.phone")}</dt><dd><bdi dir="ltr">{selected.phone}</bdi></dd></div>
              <div><dt>{t("tenantWorkspace.address")}</dt><dd>{selected.address ?? "—"}</dd></div>
              <div><dt>{t("tenantWorkspace.grade")}</dt><dd>{selected.grade ? <bdi>{selected.grade}</bdi> : t("tenantWorkspace.noGrade")}</dd></div>
            </dl>
            <small className="customer-record-id">{t("tenantWorkspace.recordId")} <bdi dir="ltr">{selected.id}</bdi></small>
            <div className="customer-actions">
              <button className="button button-secondary" onClick={() => editSelected(selected)} ref={editButton} type="button"><Icon name="edit" small />{t("common.edit")}</button>
              <button aria-expanded={linkCustomerId === selected.id} className="button button-secondary" onClick={() => setLinkCustomerId(linkCustomerId === selected.id ? undefined : selected.id)} type="button"><Icon name="shop" small />{t("customerLink.toggle")}</button>
            </div>
            {linkCustomerId === selected.id ? <CustomerLinkControls customerId={selected.id} tenantId={tenantId} /> : null}
            {/* Why this customer is on today's list (D-089); balances and receipts themselves belong to Invoices. */}
            <CustomerSignals customerId={selected.id} tenantId={tenantId} />
            <p className="muted customer-balances">{t("tenantWorkspace.balancesElsewhere")} <Link to={sectionHref("invoices", tenantId)}>{t("invoiceEditor.tab")} › {t("invoiceEditor.viewBalances")}</Link></p>
          </div>
        </article>
      ) : (
        <div className="detail customer-detail customer-detail-empty"><p className="empty-copy">{t("tenantWorkspace.noCustomerSelected")}</p></div>
      )}
    </section>
  );
}

export function TenantWorkspace({ contexts }: { contexts: TenantContext[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  // The selected business and the open section are both carried by the route's query string
  // (`tenant`, `section`) so the shell's phone bar, the desktop rail, this body and the browser
  // history all agree; the first listed business and Work are the defaults. Which
  // panels a membership gets is still read from the server's context (role, status) below.
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const context = selectedContext(contexts, tenantFromSearch(searchParams)) ?? contexts[0]!;
  const view = sectionFromSearch(searchParams);
  const setView = useCallback((next: WorkspaceSection, replace = false) => {
    setSearchParams((current) => workspaceSearch(next, tenantFromSearch(current)), { replace });
  }, [setSearchParams]);
  const chooseBusiness = (tenantId: string) => {
    const next = contexts.find((item) => item.tenant_id === tenantId);
    if (!next || next.tenant_id === context.tenant_id) return;
    // Owner sections exist only for an owner membership: a switch to a driver business lands on
    // that business's work view — its sync anchor when the owner's Offline section was open.
    const keepsSection = next.role === "owner";
    const hash = !keepsSection && view === "sync" ? `#${SYNC_ANCHOR}` : location.hash;
    void navigate({ pathname: "/workspace", search: workspaceSearch(keepsSection ? view : "work", tenantId), hash });
  };
  const [backupNotice, setBackupNotice] = useState<string>();
  const [linkCustomerId, setLinkCustomerId] = useState<string>();
  const focusCustomerId = view === "customers" ? searchParams.get("customer") : null;
  useEffect(() => {
    // Returning from the Google consent screen: open the backup desk with the outcome.
    try {
      const raw = sessionStorage.getItem(CONNECT_RESULT_KEY);
      if (!raw) return;
      sessionStorage.removeItem(CONNECT_RESULT_KEY);
      const result = JSON.parse(raw) as { tenant_id: string; email: string };
      if (result.tenant_id === context.tenant_id) { setView("backup", true); setBackupNotice(t("backup.connected", { email: result.email })); }
    } catch { /* nothing to restore */ }
  }, [context.tenant_id, setView, t]);
  const [phoneSearch, setPhoneSearch] = useState("");
  const [matches, setMatches] = useState<Customer[]>([]);
  const [customerDraft, setCustomerDraft] = useState<CustomerDraft>(emptyCustomer);
  const [editingCustomerId, setEditingCustomerId] = useState<string>();
  const [categoryDraft, setCategoryDraft] = useState<CategoryDraft>(emptyCategory);
  const [editingCategoryId, setEditingCategoryId] = useState<string>();
  const [scanBarcode, setScanBarcode] = useState("");
  const [scanResult, setScanResult] = useState<BarcodeLookupResponse>();
  const [productDraft, setProductDraft] = useState<ProductDraft>(emptyProduct);
  const [barcodeProductId, setBarcodeProductId] = useState<string>();
  const [extraBarcode, setExtraBarcode] = useState("");
  const [extraPackage, setExtraPackage] = useState<BarcodePackageLevel>("PIECE");
  const [requestError, setRequestError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setMatches([]);
    setEditingCustomerId(undefined);
    setEditingCategoryId(undefined);
    setCustomerDraft(emptyCustomer);
    setCategoryDraft(emptyCategory);
    setProductDraft(emptyProduct);
    setScanBarcode("");
    setScanResult(undefined);
    setBarcodeProductId(undefined);
    setRequestError(undefined);
    setNotice(undefined);
  }, [context.tenant_id]);

  // Customers opened from a priority, an unusual change or an assistant answer are loaded by id and
  // join the results, so the directory shows them like a search hit (the server still checks access).
  useEffect(() => {
    if (!focusCustomerId || context.role !== "owner" || matches.some((customer) => customer.id === focusCustomerId)) return;
    let current = true;
    apiRequest<Customer>(`/api/v1/tenants/${context.tenant_id}/customers/${focusCustomerId}`)
      .then((customer) => { if (current) setMatches((rows) => (rows.some((row) => row.id === customer.id) ? rows : [...rows, customer])); })
      .catch((problem: unknown) => { if (current) setRequestError(problem); });
    return () => { current = false; };
  }, [focusCustomerId, context.tenant_id, context.role, matches]);

  const categories = useQuery({
    queryKey: ["tenant-categories", context.tenant_id],
    queryFn: () =>
      apiRequest<CategoryListResponse>(
        `/api/v1/tenants/${context.tenant_id}/categories?include_archived=true`,
      ),
    enabled: context.role === "owner" && context.tenant_status === "ACTIVE",
  });

  const products = useQuery({
    queryKey: ["tenant-products", context.tenant_id],
    queryFn: () => apiRequest<TenantProductListResponse>(`/api/v1/tenants/${context.tenant_id}/products`),
    enabled: context.role === "owner" && context.tenant_status === "ACTIVE" && view === "products",
  });

  const run = async (operation: () => Promise<void>) => {
    setBusy(true);
    setRequestError(undefined);
    setNotice(undefined);
    try {
      await operation();
    } catch (error) {
      setRequestError(error);
    } finally {
      setBusy(false);
    }
  };

  const searchCustomers = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const result = await apiRequest<CustomerSearchResponse>(
        `/api/v1/tenants/${context.tenant_id}/customers/search?phone=${encodeURIComponent(phoneSearch)}`,
      );
      setMatches(result.customers);
      setNotice(t("tenantWorkspace.matches", { count: result.customers.length }));
    });
  };

  const saveCustomer = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const payload = {
        name: customerDraft.name,
        phone: customerDraft.phone,
        address: optional(customerDraft.address),
        latitude: optional(customerDraft.latitude),
        longitude: optional(customerDraft.longitude),
        grade: customerDraft.grade || null,
      };
      const path = editingCustomerId
        ? `/api/v1/tenants/${context.tenant_id}/customers/${editingCustomerId}`
        : `/api/v1/tenants/${context.tenant_id}/customers`;
      let saved: Customer;
      try {
        saved = await apiRequest<Customer>(path, {
          method: editingCustomerId ? "PUT" : "POST",
          body: JSON.stringify(payload),
        });
      } catch (problem) {
        // Offline: the row is written on this device with its command and sent once later.
        if (!isOfflineFailure(problem)) throw problem;
        const local = editingCustomerId
          ? await updateCustomerOffline(context.tenant_id, context.membership_id, editingCustomerId, { name: payload.name, phone: payload.phone, address: payload.address, grade: payload.grade })
          : await createCustomerOffline(context.tenant_id, context.membership_id, { name: payload.name, phone: payload.phone, address: payload.address, grade: payload.grade });
        setMatches((current) => [...current.filter((item) => item.id !== local.id), { ...local, phone_raw: local.phone_raw ?? local.phone } as unknown as Customer]);
        setCustomerDraft(emptyCustomer);
        setEditingCustomerId(undefined);
        setNotice(t("tenantWorkspace.customerQueuedOffline"));
        return;
      }
      setMatches((current) => {
        const withoutSaved = current.filter((item) => item.id !== saved.id);
        return [...withoutSaved, saved];
      });
      setCustomerDraft(emptyCustomer);
      setEditingCustomerId(undefined);
      setNotice(t(editingCustomerId ? "tenantWorkspace.customerUpdated" : "tenantWorkspace.customerCreated"));
    });
  };

  const editCustomer = (customer: Customer) => {
    setEditingCustomerId(customer.id);
    setCustomerDraft({
      name: customer.name,
      phone: customer.phone,
      address: customer.address ?? "",
      latitude: customer.latitude ?? "",
      longitude: customer.longitude ?? "",
      grade: customer.grade ?? "",
    });
  };

  const saveCategory = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const payload = {
        name_en: categoryDraft.name_en,
        name_ar: categoryDraft.name_ar,
        slug: categoryDraft.slug,
        display_order: Number(categoryDraft.display_order),
      };
      const path = editingCategoryId
        ? `/api/v1/tenants/${context.tenant_id}/categories/${editingCategoryId}`
        : `/api/v1/tenants/${context.tenant_id}/categories`;
      await apiRequest<Category>(path, {
        method: editingCategoryId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      await queryClient.invalidateQueries({ queryKey: ["tenant-categories", context.tenant_id] });
      setCategoryDraft(emptyCategory);
      setEditingCategoryId(undefined);
      setNotice(t(editingCategoryId ? "tenantWorkspace.categoryUpdated" : "tenantWorkspace.categoryCreated"));
    });
  };

  const editCategory = (category: Category) => {
    setEditingCategoryId(category.id);
    setCategoryDraft({
      name_en: category.name_en,
      name_ar: category.name_ar,
      slug: category.slug,
      display_order: String(category.display_order),
    });
  };

  const archiveCategory = (category: Category) => {
    void run(async () => {
      await apiRequest<Category>(
        `/api/v1/tenants/${context.tenant_id}/categories/${category.id}/archive`,
        { method: "POST" },
      );
      await queryClient.invalidateQueries({ queryKey: ["tenant-categories", context.tenant_id] });
      setNotice(t("tenantWorkspace.categoryArchived"));
    });
  };

  const scanProduct = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      try {
        const result = await apiRequest<BarcodeLookupResponse>(
          `/api/v1/tenants/${context.tenant_id}/catalog/barcodes/${encodeURIComponent(scanBarcode)}`,
        );
        setScanResult(result);
        if (result.tenant_product) {
          setNotice(t("tenantWorkspace.productAlreadyAdded"));
          return;
        }
        setProductDraft((current) => ({
          ...current,
          master_product_id: result.master_product?.id ?? null,
          name: result.master_product?.name ?? "",
          barcode: result.barcode,
          barcode_package_level: result.package_level,
        }));
        setNotice(t("tenantWorkspace.masterProductFound"));
      } catch (error) {
        if (error instanceof ApiError && error.code === "BARCODE_NOT_FOUND") {
          setScanResult(undefined);
          setProductDraft((current) => ({
            ...emptyProduct,
            category_id: current.category_id,
            barcode: scanBarcode.trim(),
          }));
          setNotice(t("tenantWorkspace.unknownBarcode"));
          return;
        }
        throw error;
      }
    });
  };

  const saveProduct = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const body = { ...productDraft, name_ar: productDraft.name_ar.trim() || null, pieces_per_box: productDraft.pieces_per_box ? Number(productDraft.pieces_per_box) : null };
      try {
        await apiRequest<TenantProduct>(`/api/v1/tenants/${context.tenant_id}/products`, {
          method: "POST",
          body: JSON.stringify(body),
        });
      } catch (problem) {
        if (!isOfflineFailure(problem)) throw problem;
        await createProductOffline(context.tenant_id, context.membership_id, body);
        setProductDraft(emptyProduct);
        setScanBarcode("");
        setScanResult(undefined);
        setNotice(t("tenantWorkspace.productQueuedOffline"));
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["tenant-products", context.tenant_id] });
      setProductDraft(emptyProduct);
      setScanBarcode("");
      setScanResult(undefined);
      setNotice(t("tenantWorkspace.productCreated"));
    });
  };

  const togglePublication = (product: TenantProduct) => {
    void run(async () => {
      try {
        await apiRequest<TenantProduct>(`/api/v1/tenants/${context.tenant_id}/products/${product.id}`, {
          method: "PUT",
          body: JSON.stringify({ is_published: !product.is_published }),
        });
      } catch (problem) {
        if (!isOfflineFailure(problem)) throw problem;
        await updateProductOffline(context.tenant_id, context.membership_id, product.id, { is_published: !product.is_published });
        setNotice(t("tenantWorkspace.productToggleQueuedOffline"));
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["tenant-products", context.tenant_id] });
      setNotice(t(product.is_published ? "tenantWorkspace.productHidden" : "tenantWorkspace.productPublished"));
    });
  };

  const addBarcode = (event: FormEvent) => {
    event.preventDefault();
    if (!barcodeProductId) return;
    void run(async () => {
      await apiRequest<TenantProduct>(
        `/api/v1/tenants/${context.tenant_id}/products/${barcodeProductId}/barcodes`,
        { method: "POST", body: JSON.stringify({ barcode: extraBarcode, package_level: extraPackage }) },
      );
      await queryClient.invalidateQueries({ queryKey: ["tenant-products", context.tenant_id] });
      setBarcodeProductId(undefined);
      setExtraBarcode("");
      setNotice(t("tenantWorkspace.barcodeAdded"));
    });
  };

  return (
    <section className="tenant-workspace" aria-label={t("tenantWorkspace.label")}>
      {/* The page heading of an active workspace: the selected business, its state and the member's
          role, with the picker beside it. Kept to one compact band so the day's work follows at once. */}
      <header className="business-head">
        <div className="business">
          <span className="avatar business-avatar" aria-hidden="true">{context.tenant_name.trim().slice(0, 1).toUpperCase()}</span>
          <div>
            <h1>{context.tenant_name}</h1>
            <div className="badge-pair"><StatusBadge value={context.tenant_status} /><StatusBadge value={context.role} /></div>
          </div>
        </div>
        {contexts.length > 1 ? (
          <label className="field tenant-picker"><span>{t("tenantWorkspace.business")}</span>
            <select value={context.tenant_id} onChange={(event) => chooseBusiness(event.target.value)}>
              {contexts.map((item) => <option key={item.tenant_id} value={item.tenant_id}>{item.tenant_name}</option>)}
            </select>
          </label>
        ) : null}
      </header>
      {/* A driver's own work needs no permission notice; it explains only an owner section requested in the address. */}
      {context.role !== "owner" && view !== "work" ? <p className="notice" role="note">{t("tenantWorkspace.ownerOnly")}</p> : null}
      {/* Keyed by business: the work screen's day meter, queued list and pickups never carry over to another membership. */}
      {context.role === "driver" && context.tenant_status === "ACTIVE" ? <><MyWorkPanel key={context.tenant_id} membershipId={context.membership_id} tenantId={context.tenant_id} /><PickupPanel key={`pickups-${context.tenant_id}`} tenantId={context.tenant_id} /></> : null}
      {context.tenant_status !== "ACTIVE" ? <div className="notice notice-error" role="alert">{t("tenantWorkspace.inactive")}</div> : null}
      {context.role === "owner" && context.tenant_status === "ACTIVE" ? (
        <>
          {/* Sections are chosen from the shell (desktop rail, phone bar and More), all carried by the address. */}
          {requestError ? <ErrorState error={requestError} /> : null}
          {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}
          {view === "customers" ? (
            // Keyed by business: an open record or form never carries over to another membership.
            <CustomerDirectory key={context.tenant_id} busy={busy} customerDraft={customerDraft} editCustomer={editCustomer} editingCustomerId={editingCustomerId} linkCustomerId={linkCustomerId} matches={matches} phoneSearch={phoneSearch} saveCustomer={saveCustomer} searchCustomers={searchCustomers} setCustomerDraft={setCustomerDraft} setEditingCustomerId={setEditingCustomerId} focusCustomerId={focusCustomerId} setLinkCustomerId={setLinkCustomerId} setPhoneSearch={setPhoneSearch} tenantId={context.tenant_id} />
          ) : view === "categories" ? (
            <div className="route-book-grid">
              <article className="content-card route-form-card">
                <p className="section-kicker">{editingCategoryId ? t("common.edit") : t("tenantWorkspace.newCategory")}</p>
                <h3>{editingCategoryId ? t("tenantWorkspace.editCategory") : t("tenantWorkspace.addCategory")}</h3>
                <form className="form-stack" onSubmit={saveCategory}>
                  <label className="field"><span>{t("tenantWorkspace.nameEn")}</span><input required value={categoryDraft.name_en} onChange={(event) => setCategoryDraft({ ...categoryDraft, name_en: event.target.value })} /></label>
                  <label className="field"><span>{t("tenantWorkspace.nameAr")}</span><input dir="rtl" required value={categoryDraft.name_ar} onChange={(event) => setCategoryDraft({ ...categoryDraft, name_ar: event.target.value })} /></label>
                  <label className="field"><span>{t("tenantWorkspace.slug")}</span><input dir="ltr" required value={categoryDraft.slug} onChange={(event) => setCategoryDraft({ ...categoryDraft, slug: event.target.value })} /></label>
                  <label className="field"><span>{t("tenantWorkspace.order")}</span><input dir="ltr" min="0" required type="number" value={categoryDraft.display_order} onChange={(event) => setCategoryDraft({ ...categoryDraft, display_order: event.target.value })} /></label>
                  <div className="form-actions"><button className="button" disabled={busy} type="submit">{t("common.saveChanges")}</button>{editingCategoryId ? <button className="button button-secondary" onClick={() => { setEditingCategoryId(undefined); setCategoryDraft(emptyCategory); }} type="button">{t("common.cancel")}</button> : null}</div>
                </form>
              </article>
              <article className="content-card lookup-card">
                <p className="section-kicker">{t("tenantWorkspace.categoryStops")}</p>
                <h3>{t("tenantWorkspace.catalogOrder")}</h3>
                {categories.isLoading ? <LoadingState /> : null}
                {categories.error ? <ErrorState error={categories.error} /> : null}
                <ol className="category-route">
                  {categories.data?.categories.map((category) => <li className={category.is_active ? "" : "is-archived"} key={category.id}><span className="category-order">{String(category.display_order).padStart(2, "0")}</span><div><strong>{category.name_en}</strong><span lang="ar" dir="rtl">{category.name_ar}</span><code dir="ltr">/{category.slug}</code></div><div className="category-actions"><button className="text-button" disabled={!category.is_active} onClick={() => editCategory(category)} type="button">{t("common.edit")}</button><button className="text-button danger-link" disabled={!category.is_active} onClick={() => archiveCategory(category)} type="button">{category.is_active ? t("tenantWorkspace.archive") : t("tenantWorkspace.archived")}</button></div></li>)}
                </ol>
              </article>
            </div>
          ) : view === "products" ? (
            <div className="catalog-workspace">
              <StorefrontSettings tenantId={context.tenant_id} />
              <CampaignPanel products={products.data?.products ?? []} tenantId={context.tenant_id} />
              <article className="content-card scan-desk">
                <p className="section-kicker">{t("tenantWorkspace.scanDesk")}</p>
                <h3>{t("tenantWorkspace.scanTitle")}</h3>
                <p>{t("tenantWorkspace.scanBody")}</p>
                <form className="inline-form" onSubmit={scanProduct}>
                  <label className="field"><span>{t("tenantWorkspace.barcode")}</span><input autoFocus dir="ltr" required value={scanBarcode} onChange={(event) => setScanBarcode(event.target.value)} /></label>
                  <button className="button" disabled={busy} type="submit">{t("tenantWorkspace.scan")}</button>
                </form>
                {scanResult?.master_product ? <div className="scan-result"><span className="status-badge status-current">{t("tenantWorkspace.masterCatalog")}</span><strong>{scanResult.master_product.name}</strong><code dir="ltr">{scanResult.barcode}</code></div> : null}
              </article>
              <GradeDiscountEditor tenantId={context.tenant_id} />
              <div className="catalog-columns">
                <article className="content-card route-form-card">
                  <p className="section-kicker">{productDraft.master_product_id ? t("tenantWorkspace.adoptProduct") : t("tenantWorkspace.manualProduct")}</p>
                  <h3>{t("tenantWorkspace.productDetails")}</h3>
                  <form className="form-grid" onSubmit={saveProduct}>
                    <label className="field field-wide"><span>{t("tenantWorkspace.productName")}</span><input required value={productDraft.name} onChange={(event) => setProductDraft({ ...productDraft, name: event.target.value })} /></label>
                    <label className="field field-wide"><span>{t("tenantWorkspace.productNameAr")}</span><input dir="rtl" value={productDraft.name_ar} onChange={(event) => setProductDraft({ ...productDraft, name_ar: event.target.value })} /></label>
                    <label className="field"><span>{t("tenantWorkspace.category")}</span><select required value={productDraft.category_id} onChange={(event) => setProductDraft({ ...productDraft, category_id: event.target.value })}><option value="">{t("tenantWorkspace.chooseCategory")}</option>{categories.data?.categories.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name_en} / {item.name_ar}</option>)}</select></label>
                    <label className="field"><span>{t("tenantWorkspace.barcode")}</span><input dir="ltr" required value={productDraft.barcode} onChange={(event) => setProductDraft({ ...productDraft, barcode: event.target.value })} /></label>
                    <label className="field"><span>{t("tenantWorkspace.packageLevel")}</span><select value={productDraft.barcode_package_level} onChange={(event) => setProductDraft({ ...productDraft, barcode_package_level: event.target.value as BarcodePackageLevel })}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
                    <label className="field"><span>{t("tenantWorkspace.tenantPrice")}</span><input dir="ltr" min="0" required step="0.0001" type="number" value={productDraft.unit_price} onChange={(event) => setProductDraft({ ...productDraft, unit_price: event.target.value })} /></label>
                    <label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} minLength={3} required value={productDraft.currency} onChange={(event) => setProductDraft({ ...productDraft, currency: event.target.value.toUpperCase() })} /></label>
                    <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span><select value={productDraft.price_basis} onChange={(event) => setProductDraft({ ...productDraft, price_basis: event.target.value as BarcodePackageLevel })}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
                    <label className="field"><span>{t("tenantWorkspace.piecesPerBox")}</span><input dir="ltr" min="1" type="number" value={productDraft.pieces_per_box} onChange={(event) => setProductDraft({ ...productDraft, pieces_per_box: event.target.value })} /></label>
                    <label className="checkbox-row field-wide"><input checked={productDraft.is_published} onChange={(event) => setProductDraft({ ...productDraft, is_published: event.target.checked })} type="checkbox" /><span>{t("tenantWorkspace.publishVisibility")}</span></label>
                    <button className="button field-wide" disabled={busy} type="submit">{t("tenantWorkspace.saveProduct")}</button>
                  </form>
                </article>
                <article className="content-card catalog-list">
                  <p className="section-kicker">{t("tenantWorkspace.tenantCatalog")}</p>
                  <h3>{t("tenantWorkspace.products")}</h3>
                  {products.isLoading ? <LoadingState /> : null}
                  {products.error ? <ErrorState error={products.error} /> : null}
                  {products.data?.products.map((product) => <article className="product-card" key={product.id}><div><h4>{product.name}</h4><span className={`status-badge ${product.is_published ? "status-current" : "status-closed"}`}>{t(product.is_published ? "tenantWorkspace.published" : "tenantWorkspace.hidden")}</span></div><strong dir="ltr">{product.unit_price} {product.currency} / {product.price_basis}</strong><div className="barcode-chips">{product.barcodes.map((barcode) => <code dir="ltr" key={`${barcode.ownership}-${barcode.id}`}>{barcode.barcode} · {barcode.package_level} · {barcode.ownership}</code>)}</div><div className="category-actions"><button className="text-button" onClick={() => togglePublication(product)} type="button">{t(product.is_published ? "tenantWorkspace.hide" : "tenantWorkspace.publish")}</button><button className="text-button" onClick={() => setBarcodeProductId(product.id)} type="button">{t("tenantWorkspace.addBarcode")}</button></div>{barcodeProductId === product.id ? <form className="inline-form barcode-form" onSubmit={addBarcode}><label className="field"><span>{t("tenantWorkspace.barcode")}</span><input dir="ltr" required value={extraBarcode} onChange={(event) => setExtraBarcode(event.target.value)} /></label><label className="field"><span>{t("tenantWorkspace.packageLevel")}</span><select value={extraPackage} onChange={(event) => setExtraPackage(event.target.value as BarcodePackageLevel)}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label><button className="button" type="submit">{t("common.saveChanges")}</button></form> : null}<ProductPricingMediaControls product={product} tenantId={context.tenant_id} /></article>)}
                </article>
              </div>
            </div>
          ) : view === "sync" ? (
            <SyncPanel tenantId={context.tenant_id} membershipId={context.membership_id} />
          ) : view === "backup" ? (
            <BackupPanel tenantId={context.tenant_id} initialNotice={backupNotice} />
          ) : view === "orders" ? (
            <OrdersPanel orderId={searchParams.get("order")} tenantId={context.tenant_id} />
          ) : view === "procurement" ? (
            <ProcurementPanel membershipId={context.membership_id} tenantId={context.tenant_id} />
          ) : view === "analytics" ? (
            <AnalyticsPanel tenantId={context.tenant_id} />
          ) : view === "assistant" ? (
            <CopilotPanel key={context.tenant_id} tenantId={context.tenant_id} />
          ) : view === "branding" ? (
            <BrandingPanel tenantId={context.tenant_id} />
          ) : view === "work" ? (
            <MyWorkPanel key={context.tenant_id} membershipId={context.membership_id} ownerBrief={<TodayBrief tenantId={context.tenant_id} />} tenantId={context.tenant_id} />
          ) : view === "deliveries" ? (
            <DeliveryPanel focusInvoiceId={searchParams.get("invoice")} key={searchParams.get("invoice") ?? "all"} tenantId={context.tenant_id} />
          ) : view === "suppliers" ? (
            <SupplierSetup membershipId={context.membership_id} tenantId={context.tenant_id} />
          ) : (
            <InvoiceEditor initialView={searchParams.get("view")} invoiceId={searchParams.get("invoice")} key={`${searchParams.get("invoice") ?? "new"}:${searchParams.get("view") ?? ""}`} tenantId={context.tenant_id} membershipId={context.membership_id} onOpenSupplierSetup={() => setView("suppliers")} />
          )}
        </>
      ) : null}
    </section>
  );
}
