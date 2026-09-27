import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import i18n from "../i18n";
import { TenantWorkspace } from "./TenantWorkspace";

const tenantId = "44444444-4444-4444-4444-444444444444";
const owner = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenantId, tenant_name: "North Route", tenant_status: "ACTIVE", role: "owner" } as const;
const category = { id: "cat-1", tenant_id: tenantId, master_category_id: null, name_en: "Drinks", name_ar: "مشروبات", slug: "drinks", display_order: 1, is_active: true, archived_at: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" };
const product = {
  id: "product-1", tenant_id: tenantId, category_id: "cat-1", master_product_id: null, name: "Cedar Water", name_ar: null,
  barcode: "5280000000012", barcodes: [], images: [], grade_prices: [], is_published: true,
  unit_price: "12.5000", currency: "USD", price_basis: "PIECE", pieces_per_box: null,
  piece_price: "12.5000", box_price: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let puts: Array<Record<string, unknown>> = [];
let refuse = false;

beforeEach(async () => {
  await i18n.changeLanguage("en");
  puts = [];
  refuse = false;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes(`/products/${product.id}`) && init?.method === "PUT") {
      puts.push(JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>);
      if (refuse) return Promise.resolve(json({ detail: { code: "GRADE_PRICES_REQUIRE_RESET", message: "Clear explicit grade prices before changing product currency or price basis" } }, 409));
      return Promise.resolve(json({ ...product, unit_price: "13.0000" }));
    }
    if (url.includes(`/tenants/${tenantId}/products`)) return Promise.resolve(json({ products: [product] }));
    if (url.includes("/categories?")) return Promise.resolve(json({ categories: [category] }));
    return Promise.resolve(json({ detail: { code: "NOT_FOUND", message: url } }, 404));
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function renderProducts() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/workspace?section=products"]}>
        <TenantWorkspace contexts={[owner]} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openEdit() {
  const card = (await screen.findByRole("heading", { level: 4, name: "Cedar Water" })).closest("article")!;
  fireEvent.click(within(card).getByRole("button", { name: "Edit" }));
  return screen.getByRole("form", { name: "Edit Cedar Water" });
}

test("an owner edits a product's price and only the changed field is sent", async () => {
  renderProducts();
  const form = await openEdit();
  expect(within(form).getByLabelText(/Arabic name/)).toHaveValue("");
  const price = within(form).getByRole("spinbutton", { name: /price/i });
  expect(price).toHaveValue(12.5);
  fireEvent.change(price, { target: { value: "13" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  expect(await screen.findByText("Product updated.")).toBeInTheDocument();
  expect(puts).toEqual([{ unit_price: "13" }]);
  expect(screen.queryByRole("form", { name: "Edit Cedar Water" })).not.toBeInTheDocument();
});

test("saving without changes sends nothing, and a grade-price conflict is explained", async () => {
  renderProducts();
  let form = await openEdit();
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  expect(puts).toEqual([]);
  expect(screen.queryByRole("form", { name: "Edit Cedar Water" })).not.toBeInTheDocument();

  refuse = true;
  form = await openEdit();
  fireEvent.change(within(form).getByLabelText("Currency"), { target: { value: "lbp" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  expect(await within(form).findByText("Clear this product's grade prices before changing its currency or price basis.")).toBeInTheDocument();
  expect(puts).toEqual([{ currency: "LBP" }]);
});
