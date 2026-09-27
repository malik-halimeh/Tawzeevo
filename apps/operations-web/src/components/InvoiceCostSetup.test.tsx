import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import i18n from "../i18n";
import { TenantWorkspace } from "./TenantWorkspace";

const tenantId = "44444444-4444-4444-4444-444444444444";
const owner = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenantId, tenant_name: "North Route", tenant_status: "ACTIVE", role: "owner" } as const;
const customer = { id: "66666666-6666-6666-6666-666666666666", tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", address: "Hamra", latitude: null, longitude: null, grade: "A", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" };
const product = {
  id: "product-1", tenant_id: tenantId, category_id: "cat", master_product_id: null, name: "Cedar Water", name_ar: null,
  barcode: "5280000000012", barcodes: [], images: [], grade_prices: [], is_published: true,
  unit_price: "12.5000", currency: "USD", price_basis: "PIECE", pieces_per_box: null,
  piece_price: "12.5000", box_price: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let costOptionCalls = 0;

beforeEach(async () => {
  await i18n.changeLanguage("en");
  costOptionCalls = 0;
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/customer-ledger/settings")) return Promise.resolve(json({ tenant_id: tenantId, customer_overdue_threshold_days: null }));
    if (url.includes("/customer-ledger/debts")) return Promise.resolve(json({ debts: [] }));
    if (url.includes("/balances")) return Promise.resolve(json({ customer_id: customer.id, customer_name: customer.name, balances: [] }));
    if (url.includes("/obligations")) return Promise.resolve(json({ customer_id: customer.id, currency: "USD", obligations: [] }));
    if (url.includes("/customers/search")) return Promise.resolve(json({ customers: [customer] }));
    if (url.includes("/catalog/barcodes/")) return Promise.resolve(json({ barcode: product.barcode, ownership: "TENANT", package_level: "PIECE", master_product: null, tenant_product: product }));
    if (url.includes("/cost-options")) { costOptionCalls += 1; return Promise.resolve(json({ options: [] })); }
    if (url.includes("/api/v1/suppliers?")) return Promise.resolve(json({ suppliers: [] }));
    if (url.includes(`/tenants/${tenantId}/products`)) return Promise.resolve(json({ products: [product] }));
    if (url.includes("/categories?")) return Promise.resolve(json({ categories: [] }));
    return Promise.resolve(json({ detail: { code: "NOT_FOUND", message: url } }, 404));
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("supplier and cost setup opened from an invoice line keeps the invoice and re-reads its missing cost", async () => {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/workspace?section=invoices"]}>
        <TenantWorkspace contexts={[owner]} />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  fireEvent.change(await screen.findByLabelText("Phone"), { target: { value: "+96170123456" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  fireEvent.change(screen.getByRole("textbox", { name: "Barcode" }), { target: { value: product.barcode } });
  fireEvent.click(screen.getByRole("button", { name: "Scan barcode" }));
  const lines = await screen.findByRole("region", { name: "Invoice lines" });
  expect(await within(lines).findByText("Cedar Water")).toBeInTheDocument();
  fireEvent.change(within(lines).getByLabelText("Quantity / calculator"), { target: { value: "7" } });
  await waitFor(() => expect(costOptionCalls).toBe(1));

  fireEvent.click(within(lines).getByRole("button", { name: "Set up suppliers and costs" }));
  expect(await screen.findByText("Supplier and cost setup — your invoice is kept as it is.")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Suppliers and product costs" })).toBeVisible();
  expect(lines).not.toBeVisible(); // hidden, not gone
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Product" })).toHaveValue(product.id));

  fireEvent.click(screen.getByRole("button", { name: "Back to the invoice" }));
  expect(screen.queryByRole("heading", { name: "Suppliers and product costs" })).not.toBeInTheDocument();
  expect(within(lines).getByLabelText("Quantity / calculator")).toHaveValue("7");
  expect(lines).toBeVisible();
  await waitFor(() => expect(costOptionCalls).toBe(2));
});
