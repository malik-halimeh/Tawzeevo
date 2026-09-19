import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { SupplierSetup } from "./SupplierSetup";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const product = {
  id: "product-1", tenant_id: "tenant", category_id: "cat", master_product_id: null, name: "Cedar Water",
  barcode: "5280000000012", barcodes: [], images: [], grade_prices: [], is_published: true,
  unit_price: "12.5000", currency: "USD", price_basis: "PIECE", pieces_per_box: 12,
  piece_price: "12.5000", box_price: "150.0000", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
};

test("owner creates a supplier, appends a cost entry and sees it preferred (FA-004 / D-041)", async () => {
  await i18n.changeLanguage("en");
  const suppliers: Record<string, unknown>[] = [];
  const entries: Record<string, unknown>[] = [];
  let preferred: string | null = null;
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    if (body) bodies.push(body);
    if (path.includes("/tenants/tenant/products")) return Promise.resolve(Response.json({ products: [product] }));
    if (path.endsWith("/supplier-purchases")) return Promise.resolve(Response.json({ purchases: [] }));
    if (path.endsWith("/supplier-ledger/totals")) return Promise.resolve(Response.json({ customers: [], suppliers: [] }));
    if (path.endsWith("/procurement/lists")) return Promise.resolve(Response.json({ lists: [] }));
    if (path.endsWith("/api/v1/suppliers?tenant_id=tenant") && init?.method === "POST") {
      suppliers.push({ id: `supplier-${suppliers.length + 1}`, tenant_id: "tenant", name: String(body?.name).trim(), contact_name: body?.contact_name ?? null, contact_phone: body?.contact_phone ?? null, address: body?.address ?? null, latitude: null, longitude: null, notes: null, version: 1, created_at: "2026-09-17T00:00:00Z", updated_at: "2026-09-17T00:00:00Z" });
      return Promise.resolve(Response.json(suppliers[suppliers.length - 1], { status: 201 }));
    }
    if (path.endsWith("/api/v1/suppliers?tenant_id=tenant")) return Promise.resolve(Response.json({ suppliers }));
    if (path.includes("/suppliers/products/product-1/costs") && init?.method === "POST") {
      entries.unshift({ id: `entry-${entries.length + 1}`, supplier_id: body?.supplier_id, unit_cost: "8.0000", currency: "USD", cost_basis: body?.cost_basis, pieces_per_box: null, effective_at: "2026-09-17T01:00:00Z", source_type: "MANUAL", notes: null, created_at: "2026-09-17T01:00:00Z" });
      preferred = preferred ?? String(body?.supplier_id);
      return Promise.resolve(Response.json({ product_id: "product-1", product_name: "Cedar Water", currency: "USD", preferred_supplier_id: preferred, entries }, { status: 201 }));
    }
    if (path.includes("/suppliers/products/product-1/costs")) {
      return Promise.resolve(Response.json({ product_id: "product-1", product_name: "Cedar Water", currency: "USD", preferred_supplier_id: preferred, entries }));
    }
    if (path.includes("/supplier-prices/products/product-1/recommendation")) {
      const ranked = entries.length === 0 ? [] : [{ rank: 1, supplier_id: "supplier-1", supplier_name: "Bekaa Wholesale", unit_cost: "8.0000", effective_at: "2026-09-17T01:00:00Z", age_days: 2, is_stale: false, source_type: "QUOTE", entry_id: "entry-1", quantity_context: "120", delta_vs_best: "0.0000", explanation: "LOWEST_COMPARABLE" }];
      return Promise.resolve(Response.json({ product_id: "product-1", currency: "USD", cost_basis: "PIECE", pieces_per_box: null, stale_after_days: 90, recommended_supplier_id: ranked[0]?.supplier_id ?? null, preferred_supplier_id: preferred, effective_supplier_id: preferred ?? ranked[0]?.supplier_id ?? null, effective_reason: ranked.length === 0 ? "NO_COMPARABLE_PRICE" : preferred === "supplier-1" ? "OWNER_CHOICE_MATCHES_RECOMMENDATION" : "LOWEST_COMPARABLE", ranked, excluded: [{ supplier_id: "supplier-9", supplier_name: "Silent", reason: "NO_PRICE", detail: "" }] }));
    }
    if (path.includes("/supplier-prices/products/product-1")) {
      const insights = entries.length === 0 ? [] : [{ supplier_id: "supplier-1", supplier_name: "Bekaa Wholesale", currency: "USD", cost_basis: "PIECE", pieces_per_box: null, latest_unit_cost: "8.0000", latest_effective_at: "2026-09-17T01:00:00Z", latest_source_type: "QUOTE", age_days: 2, lowest_unit_cost: "8.0000", highest_unit_cost: "8.0000", last_purchase_at: null, last_purchase_unit_cost: null, recent_unit_costs: ["8.0000"], entry_count: 1, variation_percent: null, stability: "INSUFFICIENT_DATA", is_preferred: true }];
      return Promise.resolve(Response.json({ product_id: "product-1", stale_after_days: 90, insights }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<SupplierSetup tenantId="tenant" />);
  expect(await screen.findByText("No suppliers yet. Add the first supplier to start recording costs.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Supplier name"), { target: { value: "Bekaa Wholesale" } });
  fireEvent.change(screen.getByLabelText("Contact person"), { target: { value: "Abu Ali" } });
  fireEvent.change(screen.getByLabelText("Contact phone"), { target: { value: "03 123 456" } });
  fireEvent.click(screen.getByRole("button", { name: "Add supplier" }));
  expect(await screen.findByText("Supplier created.")).toBeInTheDocument();
  expect(screen.getAllByText("Bekaa Wholesale").length).toBeGreaterThan(0);
  expect(bodies[0]).toMatchObject({ name: "Bekaa Wholesale", contact_name: "Abu Ali", contact_phone: "03 123 456", address: null, latitude: null });

  fireEvent.change(screen.getByLabelText("Product"), { target: { value: "product-1" } });
  expect(await screen.findByText("No cost entries for this product yet.")).toBeInTheDocument();
  expect(screen.getByText("No comparable price yet for this unit.")).toBeInTheDocument();
  fireEvent.change(screen.getAllByLabelText("Supplier")[0]!, { target: { value: "supplier-1" } });
  fireEvent.change(screen.getByLabelText("Unit cost (USD)"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("Source"), { target: { value: "QUOTE" } });
  fireEvent.change(screen.getByLabelText("For quantity (optional)"), { target: { value: "120" } });
  fireEvent.click(screen.getByRole("button", { name: "Save new cost entry" }));
  await waitFor(() => expect(screen.getByText("Cost entry saved. The invoice editor will preload it.")).toBeInTheDocument());
  expect(screen.getAllByText("Bekaa Wholesale · preferred").length).toBeGreaterThan(0);
  expect(screen.getAllByText("8.0000 USD").length).toBeGreaterThan(0);
  const cost = bodies.find((body) => body.unit_cost !== undefined);
  expect(cost).toMatchObject({ supplier_id: "supplier-1", unit_cost: "8", currency: "USD", cost_basis: "PIECE", source_type: "QUOTE", quantity_context: "120" });
  // Derived insight table: latest with source and age, no purchase yet, stability label.
  expect(await screen.findByRole("table", { name: "Price insight per supplier" })).toBeInTheDocument();
  expect(screen.getByText("no purchase yet")).toBeInTheDocument();
  expect(screen.getByText("Not enough data")).toBeInTheDocument();
  // Deterministic recommendation with an explanation, the owner's choice matching it, and the excluded supplier.
  expect(await screen.findByText("Your choice Bekaa Wholesale matches the recommendation.")).toBeInTheDocument();
  expect(screen.getByText("lowest comparable price")).toBeInTheDocument();
  expect(screen.getByText(/Silent \(no price recorded\)/)).toBeInTheDocument();
});

test("supplier setup renders Arabic labels", async () => {
  await i18n.changeLanguage("ar");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ suppliers: [], products: [], purchases: [], lists: [], customers: [] }))));
  render(<SupplierSetup tenantId="tenant" />);
  expect(await screen.findByRole("button", { name: "إضافة مورّد" })).toBeInTheDocument();
  expect(screen.getByText("المورّدون وكلف المنتجات")).toBeInTheDocument();
  await i18n.changeLanguage("en");
});
