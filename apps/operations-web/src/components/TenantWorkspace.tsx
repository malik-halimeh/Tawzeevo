import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

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
import { InvoiceEditor } from "./InvoiceEditor";
import { SupplierSetup } from "./SupplierSetup";

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

export function TenantWorkspace({ contexts }: { contexts: TenantContext[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [tenantId, setTenantId] = useState(contexts[0]?.tenant_id ?? "");
  const context = contexts.find((item) => item.tenant_id === tenantId) ?? contexts[0]!;
  const [view, setView] = useState<"customers" | "categories" | "products" | "suppliers" | "invoices">("customers");
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
  }, [tenantId]);

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
      const saved = await apiRequest<Customer>(path, {
        method: editingCustomerId ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
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
      await apiRequest<TenantProduct>(`/api/v1/tenants/${context.tenant_id}/products`, {
        method: "POST",
        body: JSON.stringify({
          ...productDraft,
          pieces_per_box: productDraft.pieces_per_box ? Number(productDraft.pieces_per_box) : null,
        }),
      });
      await queryClient.invalidateQueries({ queryKey: ["tenant-products", context.tenant_id] });
      setProductDraft(emptyProduct);
      setScanBarcode("");
      setScanResult(undefined);
      setNotice(t("tenantWorkspace.productCreated"));
    });
  };

  const togglePublication = (product: TenantProduct) => {
    void run(async () => {
      await apiRequest<TenantProduct>(`/api/v1/tenants/${context.tenant_id}/products/${product.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_published: !product.is_published }),
      });
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
      <header className="route-book-header">
        <div>
          <p className="section-kicker">{t("tenantWorkspace.routeBook")}</p>
          <h2>{context.tenant_name}</h2>
          <div className="badge-pair"><StatusBadge value={context.tenant_status} /><StatusBadge value={context.role} /></div>
        </div>
        {contexts.length > 1 ? (
          <label className="field tenant-picker"><span>{t("tenantWorkspace.business")}</span>
            <select value={context.tenant_id} onChange={(event) => setTenantId(event.target.value)}>
              {contexts.map((item) => <option key={item.tenant_id} value={item.tenant_id}>{item.tenant_name}</option>)}
            </select>
          </label>
        ) : null}
      </header>
      {context.role !== "owner" ? <div className="notice notice-error" role="alert">{t("tenantWorkspace.ownerOnly")}</div> : null}
      {context.tenant_status !== "ACTIVE" ? <div className="notice notice-error" role="alert">{t("tenantWorkspace.inactive")}</div> : null}
      {context.role === "owner" && context.tenant_status === "ACTIVE" ? (
        <>
          <div className="workspace-tabs" role="tablist" aria-label={t("tenantWorkspace.sections")}>
            <button aria-selected={view === "customers"} onClick={() => setView("customers")} role="tab" type="button">{t("tenantWorkspace.customers")}</button>
            <button aria-selected={view === "categories"} onClick={() => setView("categories")} role="tab" type="button">{t("tenantWorkspace.categories")}</button>
            <button aria-selected={view === "products"} onClick={() => setView("products")} role="tab" type="button">{t("tenantWorkspace.products")}</button>
            <button aria-selected={view === "suppliers"} onClick={() => setView("suppliers")} role="tab" type="button">{t("supplierSetup.tab")}</button>
            <button aria-selected={view === "invoices"} onClick={() => setView("invoices")} role="tab" type="button">{t("invoiceEditor.tab")}</button>
          </div>
          {requestError ? <ErrorState error={requestError} /> : null}
          {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}
          {view === "customers" ? (
            <div className="route-book-grid" role="tabpanel">
              <article className="content-card route-form-card">
                <p className="section-kicker">{editingCustomerId ? t("common.edit") : t("tenantWorkspace.newStop")}</p>
                <h3>{editingCustomerId ? t("tenantWorkspace.editCustomer") : t("tenantWorkspace.addCustomer")}</h3>
                <form className="form-grid" onSubmit={saveCustomer}>
                  <label className="field"><span>{t("tenantWorkspace.customerName")}</span><input required value={customerDraft.name} onChange={(event) => setCustomerDraft({ ...customerDraft, name: event.target.value })} /></label>
                  <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" required value={customerDraft.phone} onChange={(event) => setCustomerDraft({ ...customerDraft, phone: event.target.value })} /></label>
                  <label className="field field-wide"><span>{t("tenantWorkspace.address")}</span><input value={customerDraft.address} onChange={(event) => setCustomerDraft({ ...customerDraft, address: event.target.value })} /></label>
                  <label className="field"><span>{t("tenantWorkspace.latitude")}</span><input dir="ltr" inputMode="decimal" value={customerDraft.latitude} onChange={(event) => setCustomerDraft({ ...customerDraft, latitude: event.target.value })} /></label>
                  <label className="field"><span>{t("tenantWorkspace.longitude")}</span><input dir="ltr" inputMode="decimal" value={customerDraft.longitude} onChange={(event) => setCustomerDraft({ ...customerDraft, longitude: event.target.value })} /></label>
                  <label className="field"><span>{t("tenantWorkspace.grade")}</span><select value={customerDraft.grade} onChange={(event) => setCustomerDraft({ ...customerDraft, grade: event.target.value as CustomerDraft["grade"] })}><option value="">{t("tenantWorkspace.noGrade")}</option>{grades.map((grade) => <option key={grade}>{grade}</option>)}</select></label>
                  <div className="form-actions field-wide"><button className="button" disabled={busy} type="submit">{busy ? t("common.saving") : t("common.saveChanges")}</button>{editingCustomerId ? <button className="button button-secondary" onClick={() => { setEditingCustomerId(undefined); setCustomerDraft(emptyCustomer); }} type="button">{t("common.cancel")}</button> : null}</div>
                </form>
              </article>
              <article className="content-card lookup-card">
                <p className="section-kicker">{t("tenantWorkspace.phoneLookup")}</p>
                <h3>{t("tenantWorkspace.findCustomer")}</h3>
                <form className="inline-form" onSubmit={searchCustomers}><label className="field"><span>{t("fields.phone")}</span><input dir="ltr" required value={phoneSearch} onChange={(event) => setPhoneSearch(event.target.value)} /></label><button className="button" disabled={busy} type="submit">{t("common.search")}</button></form>
                <div className="customer-match-list">
                  {matches.map((customer) => (
                    <article className="customer-match" key={customer.id}>
                      <div><h4>{customer.name}</h4><bdi dir="ltr">{customer.phone}</bdi></div>
                      <dl><div><dt>{t("tenantWorkspace.address")}</dt><dd>{customer.address ?? "—"}</dd></div><div><dt>{t("tenantWorkspace.grade")}</dt><dd>{customer.grade ?? "—"}</dd></div><div><dt>ID</dt><dd dir="ltr">{customer.id}</dd></div></dl>
                      <button className="text-button" onClick={() => editCustomer(customer)} type="button">{t("common.edit")}</button>
                    </article>
                  ))}
                </div>
              </article>
            </div>
          ) : view === "categories" ? (
            <div className="route-book-grid" role="tabpanel">
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
            <div className="catalog-workspace" role="tabpanel">
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
          ) : view === "suppliers" ? (
            <SupplierSetup tenantId={context.tenant_id} />
          ) : (
            <InvoiceEditor tenantId={context.tenant_id} membershipId={context.membership_id} onOpenSupplierSetup={() => setView("suppliers")} />
          )}
        </>
      ) : null}
    </section>
  );
}
