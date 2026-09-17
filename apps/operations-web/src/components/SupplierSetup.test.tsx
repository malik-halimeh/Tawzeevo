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
  const suppliers: { id: string; tenant_id: string; name: string; created_at: string; updated_at: string }[] = [];
  const entries: Record<string, unknown>[] = [];
  let preferred: string | null = null;
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    if (body) bodies.push(body);
    if (path.includes("/tenants/tenant/products")) return Promise.resolve(Response.json({ products: [product] }));
    if (path.endsWith("/api/v1/suppliers?tenant_id=tenant") && init?.method === "POST") {
      suppliers.push({ id: `supplier-${suppliers.length + 1}`, tenant_id: "tenant", name: String(body?.name).trim(), created_at: "2026-09-17T00:00:00Z", updated_at: "2026-09-17T00:00:00Z" });
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
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<SupplierSetup tenantId="tenant" />);
  expect(await screen.findByText("No suppliers yet. Add the first supplier to start recording costs.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Supplier name"), { target: { value: "Bekaa Wholesale" } });
  fireEvent.click(screen.getByRole("button", { name: "Add supplier" }));
  expect(await screen.findByText("Supplier created.")).toBeInTheDocument();
  expect(screen.getByText("Bekaa Wholesale")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Product"), { target: { value: "product-1" } });
  expect(await screen.findByText("No cost entries for this product yet.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Supplier"), { target: { value: "supplier-1" } });
  fireEvent.change(screen.getByLabelText("Unit cost (USD)"), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Save new cost entry" }));
  await waitFor(() => expect(screen.getByText("Cost entry saved. The invoice editor will preload it.")).toBeInTheDocument());
  expect(screen.getByText("Bekaa Wholesale · preferred")).toBeInTheDocument();
  expect(screen.getByText("8.0000 USD")).toBeInTheDocument();
  const cost = bodies.find((body) => body.unit_cost !== undefined);
  expect(cost).toMatchObject({ supplier_id: "supplier-1", unit_cost: "8", currency: "USD", cost_basis: "PIECE" });
});

test("supplier setup renders Arabic labels", async () => {
  await i18n.changeLanguage("ar");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ suppliers: [], products: [] }))));
  render(<SupplierSetup tenantId="tenant" />);
  expect(await screen.findByRole("button", { name: "إضافة مورّد" })).toBeInTheDocument();
  expect(screen.getByText("المورّدون وكلف المنتجات")).toBeInTheDocument();
  await i18n.changeLanguage("en");
});
