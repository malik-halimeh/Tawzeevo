import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { PurchasePanel } from "./PurchasePanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const product = { id: "p1", tenant_id: "t1", category_id: "c", master_product_id: null, name: "Cedar Water", barcode: null, barcodes: [], images: [], grade_prices: [], is_published: false, unit_price: "12.5000", currency: "USD", price_basis: "PIECE", pieces_per_box: null, piece_price: "12.5000", box_price: null, created_at: "", updated_at: "" };

test("owner records a purchase with an idempotency key and sees the payable totals", async () => {
  await i18n.changeLanguage("en");
  const bodies: Record<string, unknown>[] = [];
  let purchases: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    if (body) bodies.push(body);
    if (path.endsWith("/supplier-purchases") && init?.method === "POST") {
      purchases = [{ id: "buy-1", supplier_id: "s1", supplier_name: "Bekaa", procurement_list_id: null, purchased_at: "2026-09-19T05:00:00Z", currency: "USD", total_amount: "30.0000", supplier_reference: "INV-1", reversed_at: null, reversal_reason: null, replayed: false, items: [{ id: "l1", line_number: 1, product_id: "p1", product_name: "Cedar Water", procurement_item_id: null, quantity: "4.0000", price_basis: "PIECE", pieces_per_box: null, unit_cost: "7.5000", line_total: "30.0000" }] }];
      return Promise.resolve(Response.json(purchases[0], { status: 201 }));
    }
    if (path.endsWith("/supplier-purchases")) return Promise.resolve(Response.json({ purchases }));
    if (path.endsWith("/supplier-ledger/totals")) return Promise.resolve(Response.json({ customers: [{ currency: "USD", outstanding: "25.0000", credit: "0.0000", parties: 1 }], suppliers: purchases.length ? [{ currency: "USD", outstanding: "30.0000", credit: "0.0000", parties: 1 }] : [] }));
    if (path.includes("/tenants/t1/products")) return Promise.resolve(Response.json({ products: [product] }));
    if (path.endsWith("/procurement/lists")) return Promise.resolve(Response.json({ lists: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<PurchasePanel tenantId="t1" suppliers={[{ id: "s1", name: "Bekaa" }]} />);
  expect(await screen.findByText("Owed by customers · USD")).toBeInTheDocument();
  fireEvent.change(screen.getAllByLabelText("Supplier")[0]!, { target: { value: "s1" } });
  fireEvent.change(screen.getByLabelText("Line 1 product"), { target: { value: "p1" } });
  fireEvent.change(screen.getByLabelText("Line 1 quantity"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("Line 1 unit cost"), { target: { value: "7.5" } });
  fireEvent.click(screen.getByRole("button", { name: "Record purchase" }));
  expect(await screen.findByText("Purchase recorded: 30.0000 USD added to the supplier payable.")).toBeInTheDocument();
  const sent = bodies.find((b) => b.supplier_id === "s1");
  expect(sent).toMatchObject({ currency: "USD", items: [{ product_id: "p1", quantity: "4", unit_cost: "7.5", procurement_item_id: null }] });
  expect(typeof sent?.idempotency_key).toBe("string");
  expect(await screen.findByText("Owed to suppliers · USD")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reverse" })).toBeDisabled(); // a reason is required
});

test("a recorded purchase keeps its supplier reference left to right", async () => {
  await i18n.changeLanguage("en");
  const recorded = { id: "buy-2", supplier_id: "s1", supplier_name: "Bekaa", procurement_list_id: null, purchased_at: "2026-09-19T05:00:00Z", currency: "USD", total_amount: "30.0000", supplier_reference: "BW-2026-00417", reversed_at: null, reversal_reason: null, replayed: false, items: [] };
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    if (path.endsWith("/supplier-purchases")) return Promise.resolve(Response.json({ purchases: [recorded] }));
    if (path.endsWith("/supplier-ledger/totals")) return Promise.resolve(Response.json({ customers: [], suppliers: [] }));
    if (path.includes("/tenants/t1/products")) return Promise.resolve(Response.json({ products: [product] }));
    return Promise.resolve(Response.json({ lists: [] }));
  }));

  render(<PurchasePanel tenantId="t1" suppliers={[{ id: "s1", name: "Bekaa" }]} />);
  expect(await screen.findByText("BW-2026-00417")).toHaveAttribute("dir", "ltr");
});
