import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { ProcurementPanel } from "./ProcurementPanel";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const line = (id: string, product: string, name: string, supplier: { id: string; name: string } | null, remaining: string) => ({
  id, product_id: product, product_name: name, supplier_id: supplier?.id ?? null, supplier_name: supplier?.name ?? null, price_basis: "PIECE", pieces_per_box: null,
  origin: "DEMAND", required_quantity: remaining, target_quantity: remaining, purchased_quantity: "0.0000", remaining_quantity: remaining, demand_invoice_count: 1,
  removed_at: null, remove_reason: null, waived_at: null, waive_reason: null, carried_from_item_id: null, carried_to_item_id: null, notes: null, version: 1,
  estimate: { supplier_id: "s1", supplier_name: "Bekaa", unit_cost: "8.0000", currency: "USD", age_days: 3, is_stale: false, source_type: "MANUAL", remaining_cost: "40.0000", supplier_is_recommended: false },
});
const bekaa = { id: "s1", name: "Bekaa" };
const items = [line("l1", "p1", "Cedar Water", bekaa, "5.0000"), line("l2", "p2", "Olive Oil", bekaa, "2.0000"), line("l3", "p3", "Labneh", null, "4.0000")];
const detail = { id: "list-1", status: "OPEN", title: "Friday run", demand_from: null, demand_to: null, notes: null, assignee: null, carried_from_list_id: null, version: 1, created_at: "2026-09-27T00:00:00Z", cancel_reason: null, items, estimated_totals: { USD: "56.0000" }, open_line_count: 3 };
const products = items.map((row) => ({ id: row.product_id, name: row.product_name, currency: "USD", price_basis: "PIECE", barcodes: [], images: [], grade_prices: [] }));

test("a shopping list's supplier group opens the purchase form with that supplier, list and remaining quantities, costs left to the owner", async () => {
  const purchases: Array<Record<string, unknown>> = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    if (path === "/api/v1/supplier-purchases" && init?.method === "POST") {
      purchases.push(JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>);
      return Promise.resolve(Response.json({ id: "pu1", supplier_id: "s1", supplier_name: "Bekaa", procurement_list_id: "list-1", purchased_at: "2026-09-27T10:00:00Z", currency: "USD", total_amount: "46.0000", supplier_reference: null, reversed_at: null, reversal_reason: null, replayed: false, items: [] }, { status: 201 }));
    }
    if (path === "/api/v1/procurement/lists") return Promise.resolve(Response.json({ lists: [{ id: "list-1", status: "OPEN", title: "Friday run", demand_from: null, demand_to: null, assignee: null, created_at: "2026-09-27T00:00:00Z", line_count: 3, open_line_count: 3 }] }));
    if (path === "/api/v1/procurement/lists/list-1") return Promise.resolve(Response.json(detail));
    if (path === "/api/v1/procurement/assignees") return Promise.resolve(Response.json({ assignees: [] }));
    if (path === "/api/v1/suppliers") return Promise.resolve(Response.json({ suppliers: [bekaa] }));
    if (path.endsWith("/products")) return Promise.resolve(Response.json({ products }));
    if (path === "/api/v1/supplier-purchases") return Promise.resolve(Response.json({ purchases: [] }));
    if (path === "/api/v1/supplier-ledger/totals") return Promise.resolve(Response.json({ customers: [], suppliers: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<ProcurementPanel tenantId="t1" />);
  fireEvent.click(await screen.findByRole("button", { name: /Friday run/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Record purchase from Bekaa" }));
  const form = await screen.findByRole("form", { name: "Record purchase" });
  await waitFor(() => expect(within(form).getByLabelText("Line 1 quantity")).toHaveValue(5));
  expect(within(form).getByLabelText("Line 2 quantity")).toHaveValue(2);
  expect(within(form).queryByLabelText("Line 3 quantity")).not.toBeInTheDocument(); // only this supplier's lines
  // The list's estimate for this supplier pre-fills the cost, marked until the owner checks it (D-097).
  expect(within(form).getByLabelText("Line 1 unit cost")).toHaveValue(8);
  expect(within(form).getAllByText("From the list estimate — check it")).toHaveLength(2);
  expect(screen.queryByRole("heading", { name: "Recorded purchases" })).not.toBeInTheDocument(); // the form alone, under the list

  fireEvent.change(within(form).getByLabelText("Line 1 unit cost"), { target: { value: "8" } });
  expect(within(form).getAllByText("From the list estimate — check it")).toHaveLength(1); // checked by the owner
  fireEvent.change(within(form).getByLabelText("Line 2 unit cost"), { target: { value: "3" } });
  fireEvent.click(within(form).getByRole("button", { name: "Record purchase" }));
  await waitFor(() => expect(purchases).toHaveLength(1));
  expect(purchases[0]).toMatchObject({ supplier_id: "s1", procurement_list_id: "list-1", items: [{ product_id: "p1", quantity: "5.0000", unit_cost: "8", procurement_item_id: "l1" }, { product_id: "p2", quantity: "2.0000", unit_cost: "3", procurement_item_id: "l2" }] });
  await waitFor(() => expect(screen.queryByRole("form", { name: "Record purchase" })).not.toBeInTheDocument()); // closed once recorded
  // The group without a supplier: nothing to match an estimate against, so its costs start empty.
  fireEvent.click(screen.getByRole("button", { name: "Record purchase" }));
  const other = await screen.findByRole("form", { name: "Record purchase" });
  await waitFor(() => expect(within(other).getByLabelText("Line 1 quantity")).toHaveValue(5));
  expect(within(other).getByLabelText("Line 1 unit cost")).toHaveValue(null);
});
