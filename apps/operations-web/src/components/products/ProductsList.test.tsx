import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Category, TenantProduct } from "../../api/types";
import i18n from "../../i18n";
import { createProductOffline } from "../../offline/outbox";
import { TenantWorkspace } from "../TenantWorkspace";

vi.mock("../../offline/outbox", async (original) => ({ ...await original<object>(), createProductOffline: vi.fn() }));

const tenantId = "44444444-4444-4444-4444-444444444444";
const owner = { membership_id: "m1", tenant_id: tenantId, tenant_name: "North Route", tenant_status: "ACTIVE", role: "owner" } as const;
const dates = { created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" };
const categories: Category[] = [
  { id: "drinks", name_en: "Drinks", name_ar: "مشروبات", is_active: true },
  { id: "snacks", name_en: "Snacks", name_ar: "وجبات", is_active: true },
  { id: "archived", name_en: "Archived category", name_ar: "فئة مؤرشفة", is_active: false },
].map((item, display_order) => ({ ...item, ...dates, tenant_id: tenantId, master_category_id: null, slug: item.id, display_order, archived_at: null }));
const water: TenantProduct = {
  ...dates, id: "water", tenant_id: tenantId, category_id: "drinks", master_product_id: null,
  name: "Cedar Water", name_ar: "مياه الأرز", barcode: "5280001", barcodes: [{ id: "b1", barcode: "5280001", package_level: "PIECE", ownership: "TENANT" }],
  images: [], grade_prices: [], is_published: true, unit_price: "2.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: null, piece_price: "2.0000", box_price: null,
};
let products: TenantProduct[];
let mutations: Array<{ path: string; method: string; body: Record<string, unknown> }>;
let offline = false;

beforeEach(async () => {
  await i18n.changeLanguage("en");
  localStorage.clear();
  vi.mocked(createProductOffline).mockReset();
  products = [water, { ...water, id: "chips", category_id: "snacks", name: "Olive Chips", name_ar: "رقائق الزيتون", barcode: "5280002", barcodes: [], is_published: false }];
  mutations = [];
  offline = false;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    if (init?.method === "POST" || init?.method === "PUT") {
      const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>;
      mutations.push({ path, method: init.method, body });
      if (offline) return Promise.reject(new TypeError("Failed to fetch"));
      const product = products.find((item) => path.includes(`/products/${item.id}`)) ?? water;
      if (path.endsWith(`/products/${product.id}`)) products = products.map((item) => item.id === product.id ? { ...item, ...body } : item);
      return Promise.resolve(Response.json({ ...product, ...body }));
    }
    if (path.endsWith("/categories")) return Promise.resolve(Response.json({ categories }));
    if (path.endsWith("/products")) return Promise.resolve(Response.json({ products }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function renderProducts() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={["/workspace?section=products"]}><div dir={i18n.dir()}><TenantWorkspace contexts={[owner]} /></div></MemoryRouter></QueryClientProvider>);
}
const row = (name = "Cedar Water") => screen.getByText(name, { selector: ".list-row-title" }).closest("article")!;
const names = () => Array.from(document.querySelectorAll(".list-row-title")).map((item) => item.textContent);
async function ready() { await screen.findByText("Cedar Water", { selector: ".list-row-title" }); }
function more(name = "Cedar Water") {
  fireEvent.click(within(row(name)).getByRole("button", { name: `More actions for ${name}` }));
  return within(row(name)).getByRole("group", { name: `More actions for ${name}` });
}
function filters() { fireEvent.click(screen.getByRole("button", { name: /^Filters/ })); return screen.getByRole("dialog", { name: "Filters" }); }

test("category chips filter the shown count; every category remains selectable in the sheet", async () => {
  renderProducts(); await ready();
  expect(document.querySelector(".list-head-count")).toHaveTextContent("2 products");
  const chips = screen.getByRole("group", { name: "Category" });
  expect(within(chips).queryByRole("button", { name: "Archived category" })).not.toBeInTheDocument();
  fireEvent.click(within(chips).getByRole("button", { name: "Snacks" }));
  expect(names()).toEqual(["Olive Chips"]);
  expect(document.querySelector(".list-head-count")).toHaveTextContent("1 product");
  const sheet = filters();
  expect(within(sheet).getByLabelText("Category")).toHaveValue("snacks");
  expect(within(sheet).getByRole("option", { name: /Archived category/ })).toBeInTheDocument();
  fireEvent.change(within(sheet).getByLabelText("Category"), { target: { value: "drinks" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Apply filters" }));
  expect(names()).toEqual(["Cedar Water"]);
});

test("visibility defaults to All and Published/Hidden apply locally; closing drops an unapplied choice", async () => {
  renderProducts(); await ready();
  for (const [value, expected] of [["published", ["Cedar Water"]], ["hidden", ["Olive Chips"]], ["all", ["Cedar Water", "Olive Chips"]]] as const) {
    const sheet = filters();
    fireEvent.change(within(sheet).getByLabelText("Catalog visibility"), { target: { value } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Apply filters" }));
    expect(names()).toEqual(expected);
  }
  const sheet = filters();
  fireEvent.change(within(sheet).getByLabelText("Catalog visibility"), { target: { value: "hidden" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Close" }));
  expect(within(filters()).getByLabelText("Catalog visibility")).toHaveValue("all");
  expect(mutations).toEqual([]);
});

test("search keeps its accessible name and matches English, Arabic and a package barcode", async () => {
  renderProducts(); await ready();
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  const input = screen.getByRole("searchbox", { name: "Find a product" });
  for (const query of ["CEDAR", "مياه", "5280001"]) {
    fireEvent.change(input, { target: { value: query } });
    await waitFor(() => expect(names()).toEqual(["Cedar Water"]));
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(names()).toEqual(["Cedar Water", "Olive Chips"]);
  }
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  expect(names()).toEqual(["Cedar Water", "Olive Chips"]);
});

test("row tap and menu Edit open the chosen product's pane and Back returns focus", async () => {
  renderProducts(); await ready();
  fireEvent.click(within(row("Olive Chips")).getByRole("button", { name: /Olive Chips.*Hidden/ }));
  const form = screen.getByRole("form", { name: "Edit Olive Chips" });
  expect(within(form).getByLabelText("Product name")).toHaveValue("Olive Chips");
  await waitFor(() => expect(within(form).getByLabelText("Product name")).toHaveFocus());
  expect(form.closest(".products-page")).toHaveClass("show-product-pane");
  fireEvent.click(screen.getByRole("button", { name: "Back" }));
  await waitFor(() => expect(within(row("Olive Chips")).getByRole("button", { name: /Olive Chips.*Hidden/ })).toHaveFocus());
  fireEvent.click(within(more()).getByRole("button", { name: "Edit" }));
  expect(screen.getByRole("form", { name: "Edit Cedar Water" })).toBeInTheDocument();
});

test("Hide and Publish menu actions send the existing publication update", async () => {
  renderProducts(); await ready();
  fireEvent.click(within(more()).getByRole("button", { name: "Hide" }));
  await screen.findByText("Product hidden without deleting it.");
  expect(mutations[0]).toEqual({ path: `/api/v1/tenants/${tenantId}/products/water`, method: "PUT", body: { is_published: false } });
  fireEvent.click(within(more()).getByRole("button", { name: "Publish" }));
  await screen.findByText("Product published.");
  expect(mutations[1]?.body).toEqual({ is_published: true });
});

test("Add barcode opens Manage, keeps the barcode list and submits through the existing form", async () => {
  renderProducts(); await ready();
  fireEvent.click(within(more()).getByRole("button", { name: "Add package barcode" }));
  expect(row().querySelector("details")).toHaveAttribute("open");
  expect(within(row()).getByText(/5280001/)).toBeVisible();
  const form = within(row()).getByLabelText("Barcode").closest("form")!;
  fireEvent.change(within(form).getByLabelText("Barcode"), { target: { value: "BOX-2" } });
  fireEvent.change(within(form).getByLabelText("Barcode package"), { target: { value: "BOX" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  await screen.findByText("Package barcode added.");
  expect(mutations[0]).toEqual({ path: `/api/v1/tenants/${tenantId}/products/water/barcodes`, method: "POST", body: { barcode: "BOX-2", package_level: "BOX" } });
});

test("Pricing & photos opens the existing pricing and upload controls with their handlers", async () => {
  renderProducts(); await ready();
  fireEvent.click(within(more()).getByRole("button", { name: "Pricing & photos" }));
  expect(row().querySelector("details")).toHaveAttribute("open");
  expect(within(row()).getByLabelText("Product image")).toBeVisible();
  fireEvent.change(within(row()).getByLabelText("Grade basis price"), { target: { value: "1.5" } });
  fireEvent.click(within(row()).getByRole("button", { name: "Save grade price" }));
  await waitFor(() => expect(mutations[0]).toEqual({ path: `/api/v1/tenants/${tenantId}/products/water/grade-prices/A%2B`, method: "PUT", body: { unit_price: "1.5" } }));
});

test("Fab opens the scan desk first, Back closes it and offline manual add keeps the existing outbox path", async () => {
  renderProducts(); await ready();
  fireEvent.click(document.querySelector<HTMLButtonElement>(".products-page .fab")!);
  const pane = screen.getByRole("article", { name: "Add product" });
  expect(within(pane).getByRole("heading", { name: "Scan once. Resolve the right catalog identity." })).toBeInTheDocument();
  expect(within(pane).getByLabelText("Barcode")).toHaveFocus();
  expect(within(pane).getByRole("button", { name: "Scan with camera" })).toBeInTheDocument();
  expect(pane.closest(".products-page")).toHaveClass("show-product-pane");
  fireEvent.change(within(pane).getByLabelText("Product name"), { target: { value: "Offline product" } });
  fireEvent.change(within(pane).getByLabelText("Category"), { target: { value: "drinks" } });
  fireEvent.change(within(pane).getByLabelText("Tenant price"), { target: { value: "4" } });
  offline = true;
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  fireEvent.click(within(pane).getByRole("button", { name: "Save tenant product" }));
  await screen.findByText(/the product was saved on this device/);
  expect(createProductOffline).toHaveBeenCalledWith(tenantId, owner.membership_id, expect.objectContaining({ name: "Offline product", category_id: "drinks", unit_price: "4", barcode: null, is_published: true }));
  fireEvent.click(within(pane).getByRole("button", { name: "Back" }));
  expect(screen.queryByRole("article", { name: "Add product" })).not.toBeInTheDocument();
});

test("empty matches offer Clear filters which clears search text, category and publication together", async () => {
  renderProducts(); await ready();
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.change(screen.getByLabelText("Find a product"), { target: { value: "nothing" } });
  await waitFor(() => expect(names()).toEqual([]));
  fireEvent.click(within(screen.getByRole("group", { name: "Category" })).getByRole("button", { name: "Drinks" }));
  const sheet = filters();
  fireEvent.change(within(sheet).getByLabelText("Catalog visibility"), { target: { value: "hidden" } });
  fireEvent.click(within(sheet).getByRole("button", { name: "Apply filters" }));
  fireEvent.change(screen.getByLabelText("Find a product"), { target: { value: "still nothing" } });
  expect(screen.getByText("No product matches this search.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(names()).toEqual(["Cedar Water", "Olive Chips"]);
  expect(screen.queryByLabelText("Find a product")).not.toBeInTheDocument();
  // A pending debounced search must not reapply after reset.
  await new Promise((resolve) => setTimeout(resolve, 300));
  expect(names()).toEqual(["Cedar Water", "Olive Chips"]);
  expect(within(filters()).getByLabelText("Catalog visibility")).toHaveValue("all");
});

test("an empty catalog keeps its initial state without a no-match message", async () => {
  products = [];
  renderProducts();
  await screen.findByRole("button", { name: "Drinks" });
  expect(screen.queryByText("No product matches this search.")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Clear filters" })).not.toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Add product" })).toHaveLength(2);
});

test("Arabic RTL shows both product names, translated controls and an isolated LTR price", async () => {
  await i18n.changeLanguage("ar");
  renderProducts(); await ready();
  expect(row().closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(within(row()).getByText("مياه الأرز")).toHaveAttribute("lang", "ar");
  expect(within(row()).getByText("2.0000 USD / PIECE")).toHaveAttribute("dir", "ltr");
  expect(screen.getByRole("button", { name: "مشروبات" })).toBeInTheDocument();
  fireEvent.click(within(row()).getByRole("button", { name: "إجراءات أخرى لـ Cedar Water" }));
  const menu = within(row()).getByRole("group", { name: "إجراءات أخرى لـ Cedar Water" });
  expect(within(menu).getByRole("button", { name: "الأسعار والصور" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "إضافة منتج" })).toHaveLength(2);
});
