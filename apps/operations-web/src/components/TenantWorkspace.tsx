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
  CustomerBalancesResponse,
  CustomerGrade,
  CustomerSearchResponse,
  GradeDiscount,
  GradeDiscountListResponse,
  ProductGradePrice,
  ProductImage,
  ProductPriceBasis,
  TenantContext,
  TenantProduct,
  TenantProductListResponse,
} from "../api/types";
import { AllCustomers } from "./AllCustomers";
import { ConfirmAction, ErrorState, LoadingState, StatusBadge, SuccessNotice } from "./Ui";
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
import { OwnerSetupChecklist } from "./OwnerSetupChecklist";
import { OwnerTodayStrip } from "./OwnerTodayStrip";
import { PickupPanel } from "./PickupPanel";
import { ProcurementPanel } from "./ProcurementPanel";
import { StorefrontSettings } from "./StorefrontSettings";
import { readLastChoice, rememberChoice } from "./lastChoice";
import { SyncPanel } from "./SyncPanel";
import { SYNC_ANCHOR, WORKSPACE_SECTIONS, type WorkspaceSection, groupOf, sectionFromSearch, sectionHref, selectedContext, tenantFromSearch, workspaceSearch } from "./workspaceSections";
import { useOptionalUser } from "../auth/AuthContext";
import { PENDING_ORDERS_KEY, fetchPendingOrders } from "./pendingOrders";

/** The business this member used last on this device (a convenience only; the server checks membership). */
const lastTenantKey = (userId: string) => `tawzeevo.lastTenant.${userId}`;
function readLastTenant(userId: string | undefined): string | null {
  if (!userId) return null;
  try { return localStorage.getItem(lastTenantKey(userId)); } catch { return null; }
}
function rememberTenant(userId: string | undefined, tenantId: string) {
  if (!userId) return;
  try { localStorage.setItem(lastTenantKey(userId), tenantId); } catch { /* storage unavailable: nothing to remember */ }
}

/**
 * A group's sections as tabs above the page, when the group has more than one (owners only). The
 * Orders tab repeats the shell's waiting count from the same cached query (it never fetches itself).
 */
function SectionTabs({ view, tenantParam, tenantId }: { view: WorkspaceSection; tenantParam: string | null; tenantId: string }) {
  const { t } = useTranslation();
  const pending = useQuery({ queryKey: [PENDING_ORDERS_KEY, tenantId], queryFn: () => fetchPendingOrders(tenantId), enabled: false });
  const group = groupOf(view);
  if (group.sections.length < 2) return null;
  const waiting = pending.data?.length ?? 0;
  return (
    <nav aria-label={t("nav.sectionTabs")} className="section-tabs">
      {group.sections.map((id) => {
        const meta = WORKSPACE_SECTIONS.find((entry) => entry.id === id)!;
        return (
          <Link aria-current={id === view ? "page" : undefined} className={id === view ? "active" : undefined} key={id} to={sectionHref(id, tenantParam)}>
            {t(meta.label)}
            {id === "orders" && waiting > 0 ? <span className="nav-badge"><span aria-hidden="true">{waiting}</span><span className="sr-only">{t("orders.awaitingBadge", { count: waiting })}</span></span> : null}
          </Link>
        );
      })}
    </nav>
  );
}

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
  display_order: "",
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

/** A new product starts in the category and currency used last on this device. */
function freshProduct(tenantId: string): ProductDraft {
  return { ...emptyProduct, category_id: readLastChoice("category", tenantId) ?? "", currency: readLastChoice("currency", tenantId) ?? emptyProduct.currency };
}

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

interface ProductEditDraft {
  name: string;
  name_ar: string;
  category_id: string;
  unit_price: string;
  currency: string;
  price_basis: ProductPriceBasis;
  pieces_per_box: string;
}

/**
 * Edits an existing product's name, category and price through the existing product update, sending
 * only the fields that changed (the server keeps its own rules, e.g. grade prices must be cleared
 * before the currency or price basis changes). Online only: nothing is queued from this form.
 */
function ProductEditForm({ product, tenantId, categories, onClose }: { product: TenantProduct; tenantId: string; categories: Category[]; onClose: (saved: boolean) => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<ProductEditDraft>({
    name: product.name,
    name_ar: product.name_ar ?? "",
    category_id: product.category_id,
    unit_price: product.unit_price,
    currency: product.currency,
    price_basis: product.price_basis,
    pieces_per_box: product.pieces_per_box === null ? "" : String(product.pieces_per_box),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();

  const save = (event: FormEvent) => {
    event.preventDefault();
    const changes: Record<string, unknown> = {};
    if (draft.name.trim() !== product.name) changes.name = draft.name.trim();
    if (draft.name_ar.trim() !== (product.name_ar ?? "")) changes.name_ar = draft.name_ar.trim() || null;
    if (draft.category_id !== product.category_id) changes.category_id = draft.category_id;
    if (Number(draft.unit_price) !== Number(product.unit_price)) changes.unit_price = draft.unit_price;
    if (draft.currency !== product.currency) changes.currency = draft.currency;
    if (draft.price_basis !== product.price_basis) changes.price_basis = draft.price_basis;
    const pieces = draft.pieces_per_box ? Number(draft.pieces_per_box) : null;
    if (pieces !== product.pieces_per_box) changes.pieces_per_box = pieces;
    if (!Object.keys(changes).length) { onClose(false); return; }
    setBusy(true);
    setError(undefined);
    void apiRequest<TenantProduct>(`/api/v1/tenants/${tenantId}/products/${product.id}`, { method: "PUT", body: JSON.stringify(changes) })
      .then(async () => {
        await queryClient.invalidateQueries({ queryKey: ["tenant-products", tenantId] });
        onClose(true);
      })
      .catch((problem: unknown) => setError(isOfflineFailure(problem) ? new Error(t("errors.NETWORK_UNREACHABLE")) : problem))
      .finally(() => setBusy(false));
  };

  return (
    <form aria-label={t("tenantWorkspace.editProduct", { name: product.name })} className="form-grid product-edit-form" onSubmit={save}>
      {error ? <div className="field-wide"><ErrorState error={error} /></div> : null}
      <label className="field field-wide"><span>{t("tenantWorkspace.productName")}</span><input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
      <label className="field field-wide"><span>{t("tenantWorkspace.productNameAr")}</span><input dir="rtl" value={draft.name_ar} onChange={(event) => setDraft({ ...draft, name_ar: event.target.value })} /></label>
      <label className="field"><span>{t("tenantWorkspace.category")}</span><select required value={draft.category_id} onChange={(event) => setDraft({ ...draft, category_id: event.target.value })}>{categories.filter((item) => item.is_active || item.id === product.category_id).map((item) => <option key={item.id} value={item.id}>{item.name_en} / {item.name_ar}</option>)}</select></label>
      <label className="field"><span>{t("tenantWorkspace.tenantPrice")}</span><input dir="ltr" min="0" required step="0.0001" type="number" value={draft.unit_price} onChange={(event) => setDraft({ ...draft, unit_price: event.target.value })} /></label>
      <label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} minLength={3} required value={draft.currency} onChange={(event) => setDraft({ ...draft, currency: event.target.value.toUpperCase() })} /></label>
      <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span><select value={draft.price_basis} onChange={(event) => setDraft({ ...draft, price_basis: event.target.value as ProductPriceBasis })}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
      <label className="field"><span>{t("tenantWorkspace.piecesPerBox")}</span><input dir="ltr" min="1" type="number" value={draft.pieces_per_box} onChange={(event) => setDraft({ ...draft, pieces_per_box: event.target.value })} /></label>
      <div className="form-actions field-wide"><button className="button" disabled={busy} type="submit">{busy ? t("common.saving") : t("common.saveChanges")}</button><button className="button button-secondary" disabled={busy} onClick={() => onClose(false)} type="button">{t("common.cancel")}</button></div>
    </form>
  );
}

/**
 * The customer's balance per currency (never added together) with the two things usually done next:
 * a new invoice or a payment, opened in Invoices with this customer already chosen.
 */
function CustomerBalanceActions({ tenantId, customerId }: { tenantId: string; customerId: string }) {
  const { t } = useTranslation();
  const balances = useQuery({
    queryKey: ["customer-balances", tenantId, customerId],
    queryFn: () => apiRequest<CustomerBalancesResponse>(`/api/v1/customer-ledger/customers/${customerId}/balances?tenant_id=${tenantId}`),
  });
  const rows = balances.data?.balances ?? [];
  const owed = rows.find((row) => Number(row.balance) > 0);
  return (
    <section aria-label={t("tenantWorkspace.balanceLabel")} className="customer-balance">
      <p className="eyebrow">{t("tenantWorkspace.balanceLabel")}</p>
      {balances.isLoading ? <p className="muted">{t("common.loading")}</p> : rows.length ? (
        <div className="balance-chips">{rows.map((row) => <span dir="ltr" key={row.currency}>{row.balance} {row.currency}</span>)}</div>
      ) : balances.error ? null : <p className="muted">{t("invoiceEditor.noLedgerBalance")}</p>}
      <div className="customer-actions">
        <Link className="button" to={sectionHref("invoices", tenantId, { customer: customerId })}><Icon name="invoice" small />{t("tenantWorkspace.newInvoice")}</Link>
        <Link className="button button-secondary" to={sectionHref("invoices", tenantId, { customer: customerId, view: "payments", currency: owed?.currency ?? null })}><Icon name="coin" small />{t("tenantWorkspace.recordPayment")}</Link>
      </div>
    </section>
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
  // The phone of the last finished search, offered for "Add customer with this phone" when nothing matched.
  const [searchedPhone, setSearchedPhone] = useState("");
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
    setSearchedPhone(phoneSearch.trim());
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
  const addCustomer = (phone?: string) => {
    rememberListScroll();
    discardForm(); // an edit left open never leaks into a new customer
    if (phone) setCustomerDraft({ ...emptyCustomer, phone });
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
          <button className="button customer-add" onClick={() => addCustomer()} ref={addButton} type="button"><Icon name="plus" small />{t("tenantWorkspace.addCustomer")}</button>
          {searchedPhone && !busy && matches.length === 0 ? <button className="button button-secondary" onClick={() => addCustomer(searchedPhone)} type="button"><Icon name="plus" small />{t("tenantWorkspace.addWithPhone", { phone: searchedPhone })}</button> : null}
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
        <AllCustomers tenantId={tenantId} />
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
            <CustomerBalanceActions customerId={selected.id} tenantId={tenantId} />
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
  const user = useOptionalUser();
  const context = selectedContext(contexts, tenantFromSearch(searchParams)) ?? contexts[0]!;
  const view = sectionFromSearch(searchParams);
  // Entering the workspace without a business in the address: continue with the one used last on
  // this device (when this member still belongs to it). Only on entry: afterwards an address without
  // a business keeps meaning the first one (e.g. the browser's Back), as the links assume.
  const addressTenant = tenantFromSearch(searchParams);
  const enteredOnce = useRef(false);
  useEffect(() => {
    if (enteredOnce.current) return;
    enteredOnce.current = true;
    if (addressTenant) return;
    const last = readLastTenant(user?.id);
    if (last && last !== contexts[0]?.tenant_id && contexts.some((item) => item.tenant_id === last)) {
      void navigate({ pathname: "/workspace", search: workspaceSearch(view, last), hash: location.hash }, { replace: true });
    }
  }, [addressTenant, contexts, location.hash, navigate, user?.id, view]);
  useEffect(() => { rememberTenant(user?.id, context.tenant_id); }, [user?.id, context.tenant_id]);
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
  // Supplier and cost setup opened from an invoice line: shown in place of the invoice while the
  // editor stays mounted (hidden), so nothing typed is lost; closing it re-reads the missing costs.
  const [costSetup, setCostSetup] = useState<{ productId?: string } | null>(null);
  const [costsRefreshKey, setCostsRefreshKey] = useState(0);
  useEffect(() => { setCostSetup(null); }, [view, context.tenant_id]);
  const closeCostSetup = () => {
    setCostSetup(null);
    setCostsRefreshKey((key) => key + 1);
  };
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
  const [editingProductId, setEditingProductId] = useState<string>();
  // Products: the list comes first (search and category filter over the loaded list); adding opens on demand.
  const [addingProduct, setAddingProduct] = useState(false);
  const [productQuery, setProductQuery] = useState("");
  const [productCategory, setProductCategory] = useState("");
  const [quickCategory, setQuickCategory] = useState<{ open: boolean; name_en: string; name_ar: string }>({ open: false, name_en: "", name_ar: "" });
  const [extraBarcode, setExtraBarcode] = useState("");
  const [extraPackage, setExtraPackage] = useState<BarcodePackageLevel>("PIECE");
  const [requestError, setRequestError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);

  // A result notice belongs to the section that produced it.
  useEffect(() => { setNotice(undefined); setRequestError(undefined); }, [view]);

  useEffect(() => {
    setMatches([]);
    setEditingCustomerId(undefined);
    setEditingCategoryId(undefined);
    setCustomerDraft(emptyCustomer);
    setCategoryDraft(emptyCategory);
    setProductDraft(freshProduct(context.tenant_id));
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
    enabled: context.role === "owner" && context.tenant_status === "ACTIVE" && (view === "products" || view === "storefront"),
  });
  const activeCategories = categories.data?.categories.filter((item) => item.is_active) ?? [];
  // A new category is placed after the others unless the owner gives an order.
  const nextCategoryOrder = Math.max(0, ...(categories.data?.categories.map((item) => item.display_order) ?? [])) + 1;
  // A remembered category that is no longer active is not offered.
  useEffect(() => {
    if (!categories.data || !productDraft.category_id) return;
    if (!categories.data.categories.some((item) => item.is_active && item.id === productDraft.category_id)) setProductDraft((draft) => ({ ...draft, category_id: "" }));
  }, [categories.data, productDraft.category_id]);
  const productNeedle = productQuery.trim().toLowerCase();
  const shownProducts = (products.data?.products ?? []).filter((product) =>
    (!productCategory || product.category_id === productCategory)
    && (!productNeedle || product.name.toLowerCase().includes(productNeedle) || (product.name_ar ?? "").toLowerCase().includes(productNeedle) || product.barcodes.some((barcode) => barcode.barcode.toLowerCase().includes(productNeedle))));

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
        // Left empty, the web address comes from the English name (the server normalises it the same way).
        slug: categoryDraft.slug.trim() || categoryDraft.name_en,
        display_order: categoryDraft.display_order === "" ? nextCategoryOrder : Number(categoryDraft.display_order),
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

  const restoreCategory = (category: Category) => {
    void run(async () => {
      await apiRequest<Category>(
        `/api/v1/tenants/${context.tenant_id}/categories/${category.id}/restore`,
        { method: "POST" },
      );
      await queryClient.invalidateQueries({ queryKey: ["tenant-categories", context.tenant_id] });
      setNotice(t("tenantWorkspace.categoryRestored"));
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
            currency: current.currency,
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
        rememberChoice("category", context.tenant_id, body.category_id);
        rememberChoice("currency", context.tenant_id, body.currency);
        setProductDraft(freshProduct(context.tenant_id));
        setScanBarcode("");
        setScanResult(undefined);
        setNotice(t("tenantWorkspace.productQueuedOffline"));
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["tenant-products", context.tenant_id] });
      rememberChoice("category", context.tenant_id, body.category_id);
      rememberChoice("currency", context.tenant_id, body.currency);
      setProductDraft(freshProduct(context.tenant_id));
      setScanBarcode("");
      setScanResult(undefined);
      setNotice(t("tenantWorkspace.productCreated"));
    });
  };

  // A category created from the product form: same create call, name as its web address, placed last.
  const createQuickCategory = () => {
    if (!quickCategory.name_en.trim() || !quickCategory.name_ar.trim()) return;
    void run(async () => {
      const created = await apiRequest<Category>(`/api/v1/tenants/${context.tenant_id}/categories`, {
        method: "POST",
        body: JSON.stringify({ name_en: quickCategory.name_en, name_ar: quickCategory.name_ar, slug: quickCategory.name_en, display_order: nextCategoryOrder }),
      });
      await queryClient.invalidateQueries({ queryKey: ["tenant-categories", context.tenant_id] });
      setProductDraft((draft) => ({ ...draft, category_id: created.id }));
      setQuickCategory({ open: false, name_en: "", name_ar: "" });
      setNotice(t("tenantWorkspace.categoryCreated"));
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
          <SectionTabs tenantId={context.tenant_id} tenantParam={addressTenant} view={view} />
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
                  <details className="more-options" open={editingCategoryId ? true : undefined}>
                    <summary>{t("tenantWorkspace.moreOptions")}</summary>
                    <label className="field"><span>{t("tenantWorkspace.slug")}</span><input dir="ltr" placeholder={categoryDraft.name_en} value={categoryDraft.slug} onChange={(event) => setCategoryDraft({ ...categoryDraft, slug: event.target.value })} /></label>
                    <small className="muted">{t("tenantWorkspace.slugAuto")}</small>
                    <label className="field"><span>{t("tenantWorkspace.order")}</span><input dir="ltr" min="0" placeholder={String(nextCategoryOrder)} type="number" value={categoryDraft.display_order} onChange={(event) => setCategoryDraft({ ...categoryDraft, display_order: event.target.value })} /></label>
                    <small className="muted">{t("tenantWorkspace.orderAuto")}</small>
                  </details>
                  <div className="form-actions"><button className="button" disabled={busy} type="submit">{t("common.saveChanges")}</button>{editingCategoryId ? <button className="button button-secondary" onClick={() => { setEditingCategoryId(undefined); setCategoryDraft(emptyCategory); }} type="button">{t("common.cancel")}</button> : null}</div>
                </form>
              </article>
              <article className="content-card lookup-card">
                <p className="section-kicker">{t("tenantWorkspace.categoryStops")}</p>
                <h3>{t("tenantWorkspace.catalogOrder")}</h3>
                {categories.isLoading ? <LoadingState /> : null}
                {categories.error ? <ErrorState error={categories.error} /> : null}
                <ol className="category-route">
                  {categories.data?.categories.map((category) => <li className={category.is_active ? "" : "is-archived"} key={category.id}><span className="category-order">{String(category.display_order).padStart(2, "0")}</span><div><strong>{category.name_en}</strong><span lang="ar" dir="rtl">{category.name_ar}</span><code dir="ltr">/{category.slug}</code></div><div className="category-actions"><button className="text-button" disabled={!category.is_active} onClick={() => editCategory(category)} type="button">{t("common.edit")}</button>{category.is_active ? <ConfirmAction className="text-button danger-link" confirmLabel={t("tenantWorkspace.confirmArchive")} danger disabled={busy} label={t("tenantWorkspace.archive")} onConfirm={() => archiveCategory(category)}>{t("tenantWorkspace.archiveExplain")}</ConfirmAction> : <><span className="status-badge">{t("tenantWorkspace.archived")}</span><button className="text-button" disabled={busy} onClick={() => restoreCategory(category)} type="button">{t("tenantWorkspace.restore")}</button></>}</div></li>)}
                </ol>
              </article>
            </div>
          ) : view === "products" ? (
            <div className="catalog-workspace">
              <div className="catalog-toolbar">
                <label className="field"><span>{t("tenantWorkspace.productSearch")}</span><input type="search" value={productQuery} onChange={(event) => setProductQuery(event.target.value)} /></label>
                <label className="field"><span>{t("tenantWorkspace.category")}</span><select value={productCategory} onChange={(event) => setProductCategory(event.target.value)}><option value="">{t("tenantWorkspace.allCategories")}</option>{categories.data?.categories.map((item) => <option key={item.id} value={item.id}>{item.name_en} / {item.name_ar}</option>)}</select></label>
                <button aria-expanded={addingProduct} className="button" onClick={() => setAddingProduct(!addingProduct)} type="button"><Icon name="plus" small />{t("tenantWorkspace.addProduct")}</button>
              </div>
              {addingProduct ? (
                <article className="content-card add-product">
                  <div className="scan-desk">
                    <p className="section-kicker">{t("tenantWorkspace.scanDesk")}</p>
                    <h3>{t("tenantWorkspace.scanTitle")}</h3>
                    <form className="inline-form" onSubmit={scanProduct}>
                      <label className="field"><span>{t("tenantWorkspace.barcode")}</span><input autoFocus dir="ltr" required value={scanBarcode} onChange={(event) => setScanBarcode(event.target.value)} /></label>
                      <button className="button" disabled={busy} type="submit">{t("tenantWorkspace.scan")}</button>
                    </form>
                    {scanResult?.master_product ? <div className="scan-result"><span className="status-badge status-current">{t("tenantWorkspace.masterCatalog")}</span><strong>{scanResult.master_product.name}</strong><code dir="ltr">{scanResult.barcode}</code></div> : null}
                  </div>
                  <div className="route-form-card">
                    <p className="section-kicker">{productDraft.master_product_id ? t("tenantWorkspace.adoptProduct") : t("tenantWorkspace.manualProduct")}</p>
                    <h3>{t("tenantWorkspace.productDetails")}</h3>
                    <form className="form-grid" onSubmit={saveProduct}>
                      <label className="field field-wide"><span>{t("tenantWorkspace.productName")}</span><input required value={productDraft.name} onChange={(event) => setProductDraft({ ...productDraft, name: event.target.value })} /></label>
                      <label className="field"><span>{t("tenantWorkspace.category")}</span><select required value={productDraft.category_id} onChange={(event) => setProductDraft({ ...productDraft, category_id: event.target.value })}><option value="">{t("tenantWorkspace.chooseCategory")}</option>{activeCategories.map((item) => <option key={item.id} value={item.id}>{item.name_en} / {item.name_ar}</option>)}</select></label>
                      <div className="field quick-category">
                        <button aria-expanded={quickCategory.open} className="text-button" onClick={() => setQuickCategory({ ...quickCategory, open: !quickCategory.open })} type="button"><Icon name="plus" small />{t("tenantWorkspace.newCategoryInline")}</button>
                        {quickCategory.open ? (
                          <div className="quick-category-fields" role="group" aria-label={t("tenantWorkspace.newCategoryInline")}>
                            <label className="field"><span>{t("tenantWorkspace.nameEn")}</span><input value={quickCategory.name_en} onChange={(event) => setQuickCategory({ ...quickCategory, name_en: event.target.value })} /></label>
                            <label className="field"><span>{t("tenantWorkspace.nameAr")}</span><input dir="rtl" value={quickCategory.name_ar} onChange={(event) => setQuickCategory({ ...quickCategory, name_ar: event.target.value })} /></label>
                            <button className="button button-secondary" disabled={busy || !quickCategory.name_en.trim() || !quickCategory.name_ar.trim()} onClick={createQuickCategory} type="button">{t("tenantWorkspace.saveCategory")}</button>
                          </div>
                        ) : null}
                      </div>
                      <label className="field"><span>{t("tenantWorkspace.barcode")}</span><input dir="ltr" required value={productDraft.barcode} onChange={(event) => setProductDraft({ ...productDraft, barcode: event.target.value })} /></label>
                      <label className="field"><span>{t("tenantWorkspace.tenantPrice")}</span><input dir="ltr" min="0" required step="0.0001" type="number" value={productDraft.unit_price} onChange={(event) => setProductDraft({ ...productDraft, unit_price: event.target.value })} /></label>
                      <details className="more-options field-wide">
                        <summary>{t("tenantWorkspace.moreOptions")}</summary>
                        <div className="form-grid">
                          <label className="field field-wide"><span>{t("tenantWorkspace.productNameAr")}</span><input dir="rtl" value={productDraft.name_ar} onChange={(event) => setProductDraft({ ...productDraft, name_ar: event.target.value })} /></label>
                          <label className="field"><span>{t("tenantWorkspace.packageLevel")}</span><select value={productDraft.barcode_package_level} onChange={(event) => setProductDraft({ ...productDraft, barcode_package_level: event.target.value as BarcodePackageLevel })}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
                          <label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} minLength={3} required value={productDraft.currency} onChange={(event) => setProductDraft({ ...productDraft, currency: event.target.value.toUpperCase() })} /></label>
                          <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span><select value={productDraft.price_basis} onChange={(event) => setProductDraft({ ...productDraft, price_basis: event.target.value as BarcodePackageLevel })}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
                          <label className="field"><span>{t("tenantWorkspace.piecesPerBox")}</span><input dir="ltr" min="1" type="number" value={productDraft.pieces_per_box} onChange={(event) => setProductDraft({ ...productDraft, pieces_per_box: event.target.value })} /></label>
                          <label className="checkbox-row field-wide"><input checked={productDraft.is_published} onChange={(event) => setProductDraft({ ...productDraft, is_published: event.target.checked })} type="checkbox" /><span>{t("tenantWorkspace.publishVisibility")}</span></label>
                        </div>
                      </details>
                      <button className="button field-wide" disabled={busy} type="submit">{t("tenantWorkspace.saveProduct")}</button>
                    </form>
                  </div>
                </article>
              ) : null}
              <article className="content-card catalog-list">
                <p className="section-kicker">{t("tenantWorkspace.tenantCatalog")}</p>
                <h3>{t("tenantWorkspace.products")}</h3>
                {products.isLoading ? <LoadingState /> : null}
                {products.error ? <ErrorState error={products.error} /> : null}
                {products.data?.products.length && !shownProducts.length ? <p className="muted">{t("tenantWorkspace.noProductMatch")}</p> : null}
                {shownProducts.map((product) => (
                  <article className="product-card" key={product.id}>
                    <div><h4>{product.name}</h4><span className={`status-badge ${product.is_published ? "status-current" : "status-closed"}`}>{t(product.is_published ? "tenantWorkspace.published" : "tenantWorkspace.hidden")}</span></div>
                    <strong dir="ltr">{product.unit_price} {product.currency} / {product.price_basis}</strong>
                    <div className="category-actions">
                      <button className="text-button" onClick={() => togglePublication(product)} type="button">{t(product.is_published ? "tenantWorkspace.hide" : "tenantWorkspace.publish")}</button>
                      <button aria-expanded={editingProductId === product.id} className="text-button" onClick={() => { setNotice(undefined); setEditingProductId(editingProductId === product.id ? undefined : product.id); }} type="button">{t("common.edit")}</button>
                    </div>
                    {editingProductId === product.id ? <ProductEditForm categories={categories.data?.categories ?? []} onClose={(saved) => { setEditingProductId(undefined); if (saved) setNotice(t("tenantWorkspace.productUpdated")); }} product={product} tenantId={context.tenant_id} /> : null}
                    <details className="product-manage">
                      <summary>{t("common.manage")}</summary>
                      <div className="barcode-chips">{product.barcodes.map((barcode) => <code dir="ltr" key={`${barcode.ownership}-${barcode.id}`}>{barcode.barcode} · {barcode.package_level} · {barcode.ownership}</code>)}</div>
                      <button className="text-button" onClick={() => setBarcodeProductId(product.id)} type="button">{t("tenantWorkspace.addBarcode")}</button>
                      {barcodeProductId === product.id ? <form className="inline-form barcode-form" onSubmit={addBarcode}><label className="field"><span>{t("tenantWorkspace.barcode")}</span><input dir="ltr" required value={extraBarcode} onChange={(event) => setExtraBarcode(event.target.value)} /></label><label className="field"><span>{t("tenantWorkspace.packageLevel")}</span><select value={extraPackage} onChange={(event) => setExtraPackage(event.target.value as BarcodePackageLevel)}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label><button className="button" type="submit">{t("common.saveChanges")}</button></form> : null}
                      <ProductPricingMediaControls product={product} tenantId={context.tenant_id} />
                    </details>
                  </article>
                ))}
              </article>
            </div>
          ) : view === "pricing" ? (
            <GradeDiscountEditor tenantId={context.tenant_id} />
          ) : view === "storefront" ? (
            <div className="catalog-workspace">
              <StorefrontSettings tenantId={context.tenant_id} />
              <CampaignPanel products={products.data?.products ?? []} tenantId={context.tenant_id} />
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
            <MyWorkPanel key={context.tenant_id} membershipId={context.membership_id} ownerBrief={<><OwnerSetupChecklist tenantId={context.tenant_id} /><OwnerTodayStrip tenantId={context.tenant_id} /><TodayBrief tenantId={context.tenant_id} /></>} tenantId={context.tenant_id} />
          ) : view === "deliveries" ? (
            <DeliveryPanel focusInvoiceId={searchParams.get("invoice")} key={searchParams.get("invoice") ?? "all"} tenantId={context.tenant_id} />
          ) : view === "suppliers" ? (
            <SupplierSetup membershipId={context.membership_id} tenantId={context.tenant_id} />
          ) : (
            <>
              {costSetup ? (
                <div className="cost-setup-in-place">
                  <div className="revision-bar">
                    <p>{t("invoiceEditor.costSetupFromInvoice")}</p>
                    <button className="text-button" onClick={closeCostSetup} type="button"><Arrow back small />{t("invoiceEditor.backToInvoice")}</button>
                  </div>
                  <SupplierSetup key={costSetup.productId ?? "none"} membershipId={context.membership_id} tenantId={context.tenant_id} {...(costSetup.productId ? { initialProductId: costSetup.productId } : {})} />
                </div>
              ) : null}
              <div hidden={costSetup !== null}>
                <InvoiceEditor costsRefreshKey={costsRefreshKey} customerId={searchParams.get("customer")} initialCurrency={searchParams.get("currency")} initialView={searchParams.get("view")} invoiceId={searchParams.get("invoice")} key={`${searchParams.get("invoice") ?? "new"}:${searchParams.get("view") ?? ""}:${searchParams.get("customer") ?? ""}:${searchParams.get("fresh") ?? ""}`} tenantId={context.tenant_id} membershipId={context.membership_id} onOpenSupplierSetup={(productId) => { setCostSetup(productId ? { productId } : {}); window.scrollTo({ top: 0 }); }} />
              </div>
            </>
          )}
        </>
      ) : null}
    </section>
  );
}
