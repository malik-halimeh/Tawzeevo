import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { TenantWorkspace } from "./TenantWorkspace";

const tenantId = "44444444-4444-4444-4444-444444444444";
const owner = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenantId, tenant_name: "North Route", tenant_status: "ACTIVE", role: "owner" } as const;
const category = (id: string, name_en: string, name_ar: string, display_order: number) => ({ id, tenant_id: tenantId, master_category_id: null, name_en, name_ar, slug: name_en.toLowerCase(), display_order, is_active: true, archived_at: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" });
const product = (id: string, name: string, category_id: string, barcode: string) => ({
  id, tenant_id: tenantId, category_id, master_product_id: null, name, name_ar: null, barcode, barcodes: [{ id: `b-${id}`, barcode, package_level: "PIECE", ownership: "TENANT" }],
  images: [], grade_prices: [], is_published: true, unit_price: "2.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: null, piece_price: "2.0000", box_price: null,
  created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
});

let categories: ReturnType<typeof category>[] = [];
let posts: Array<{ path: string; body: Record<string, unknown> }> = [];

beforeEach(async () => {
  await i18n.changeLanguage("en");
  localStorage.clear();
  categories = [category("c-drinks", "Drinks", "مشروبات", 4), category("c-snacks", "Snacks", "وجبات", 9)];
  posts = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost");
    if (init?.method === "POST") {
      const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>;
      posts.push({ path: url.pathname, body });
      if (url.pathname.endsWith("/categories")) {
        const created = category("c-new", String(body.name_en), String(body.name_ar), Number(body.display_order));
        categories = [...categories, created];
        return Promise.resolve(Response.json(created, { status: 201 }));
      }
      return Promise.resolve(Response.json(product("p-new", String(body.name), String(body.category_id), String(body.barcode)), { status: 201 }));
    }
    if (url.pathname.endsWith("/categories")) return Promise.resolve(Response.json({ categories }));
    if (url.pathname.endsWith("/products")) return Promise.resolve(Response.json({ products: [product("p1", "Cedar Water", "c-drinks", "5280001"), product("p2", "Olive Chips", "c-snacks", "5280002")] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const renderSection = (section: string) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[`/workspace?section=${section}`]}><TenantWorkspace contexts={[owner]} /></MemoryRouter>
  </QueryClientProvider>,
);
const productNames = () => screen.queryAllByRole("heading", { level: 4 }).map((heading) => heading.textContent);

test("the product list comes first and is found by typing or by category, with settings on their own tabs", async () => {
  renderSection("products");
  await waitFor(() => expect(productNames()).toEqual(["Cedar Water", "Olive Chips"]));
  expect(screen.queryByRole("heading", { name: "Scan once. Resolve the right catalog identity." })).not.toBeInTheDocument();
  expect(screen.queryByText(/Customer access policy/)).not.toBeInTheDocument(); // storefront settings live in Settings
  expect(screen.queryByLabelText("Grade A discount (%)")).not.toBeInTheDocument(); // grade discounts live in Pricing
  fireEvent.change(screen.getByLabelText("Find a product"), { target: { value: "olive" } });
  expect(productNames()).toEqual(["Olive Chips"]);
  fireEvent.change(screen.getByLabelText("Find a product"), { target: { value: "5280001" } });
  expect(productNames()).toEqual(["Cedar Water"]); // by barcode too
  fireEvent.change(screen.getByLabelText("Find a product"), { target: { value: "" } });
  fireEvent.change(within(screen.getByRole("button", { name: "Add product" }).parentElement!).getByLabelText("Category"), { target: { value: "c-snacks" } });
  expect(productNames()).toEqual(["Olive Chips"]);
});

test("a new product starts in the category and currency used last, and a missing category is created from the form", async () => {
  localStorage.setItem(`tawzeevo.last.category.${tenantId}`, "c-snacks");
  localStorage.setItem(`tawzeevo.last.currency.${tenantId}`, "LBP");
  renderSection("products");
  fireEvent.click(await screen.findByRole("button", { name: "Add product" }));
  const form = screen.getByRole("heading", { name: "Product details" }).closest("div")!;
  await waitFor(() => expect(within(form).getByLabelText("Category")).toHaveValue("c-snacks"));
  expect(within(form).getByLabelText("Currency")).toHaveValue("LBP");

  fireEvent.click(within(form).getByRole("button", { name: "New category" }));
  const quick = within(form).getByRole("group", { name: "New category" });
  fireEvent.change(within(quick).getByLabelText("English name"), { target: { value: "Frozen food" } });
  fireEvent.change(within(quick).getByLabelText("Arabic name"), { target: { value: "أطعمة مجمدة" } });
  fireEvent.click(within(quick).getByRole("button", { name: "Save category" }));
  await waitFor(() => expect(within(form).getByLabelText("Category")).toHaveValue("c-new"));
  expect(posts[0]).toEqual({ path: `/api/v1/tenants/${tenantId}/categories`, body: { name_en: "Frozen food", name_ar: "أطعمة مجمدة", slug: "Frozen food", display_order: 10 } });

  fireEvent.change(within(form).getByLabelText("Product name"), { target: { value: "Frozen peas" } });
  fireEvent.change(within(form).getByLabelText("Barcode"), { target: { value: "5280009" } });
  fireEvent.change(within(form).getByLabelText("Tenant price"), { target: { value: "3" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save tenant product" }));
  await waitFor(() => expect(posts[1]?.body).toMatchObject({ category_id: "c-new", currency: "LBP", name: "Frozen peas" }));
  expect(localStorage.getItem(`tawzeevo.last.category.${tenantId}`)).toBe("c-new");
});

test("a category needs only its two names: the web address comes from the English name and it is placed last", async () => {
  renderSection("categories");
  fireEvent.change(await screen.findByLabelText("English name"), { target: { value: "Cold drinks" } });
  fireEvent.change(screen.getByLabelText("Arabic name"), { target: { value: "مشروبات باردة" } });
  await waitFor(() => expect(screen.getByLabelText("Display order")).toHaveAttribute("placeholder", "10"));
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(posts[0]?.body).toEqual({ name_en: "Cold drinks", name_ar: "مشروبات باردة", slug: "Cold drinks", display_order: 10 }));
});
