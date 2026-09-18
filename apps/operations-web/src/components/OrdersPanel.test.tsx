import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OrdersPanel } from "./OrdersPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("owner links a suggested customer explicitly, then confirms the order", async () => {
  await i18n.changeLanguage("en");
  const order = {
    id: "o1", status: "RECEIVED", contact_name: "Rami", contact_phone: "+96170000001", contact_address: "Tripoli", notes: null, currency: "USD",
    intended_customer_id: "c1", intended_assurance: "LINK", linked_customer_id: null as string | null, invoice_id: "inv1", delivery_date: null,
    decision_note: null, created_at: "2026-09-19T00:00:00Z", decided_at: null as string | null,
  };
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    calls.push(`${init?.method ?? "GET"} ${path.split("?")[0]}`);
    if (path.includes("/notifications")) return Promise.resolve(Response.json({ notifications: [], unread: 1 }));
    if (path.endsWith("/orders") || path.includes("/orders?")) return Promise.resolve(Response.json({ orders: [order] }));
    const invoice = { id: "inv1", status: "DRAFT", current_revision_id: order.linked_customer_id ? "rev-2" : "rev-1", official_invoice_number: null, net_sales: "8.50", currency: "USD", items: [{ id: "l1", product_name: "Water", quantity: "1", effective_unit_price: "8.50", line_total: "8.50" }] };
    if (path.includes("/link-customer")) { order.linked_customer_id = "c1"; }
    if (path.includes("/confirm")) {
      expect(JSON.parse(init?.body as string)).toEqual({ expected_revision_id: "rev-2" }); // the re-priced revision, never the stale one
      order.status = "CONFIRMED"; order.decided_at = "2026-09-19T01:00:00Z";
    }
    if (path.includes("/orders/o1")) return Promise.resolve(Response.json({ order, invoice, candidates: [{ id: "c1", name: "Rami Store", phone: "+96170000001", grade: "A", is_hint: true }], cancellation_requests: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<OrdersPanel tenantId="t1" />);
  expect(await screen.findByText("1 new")).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /Rami/ }));
  expect(await screen.findByText("Water")).toBeInTheDocument();
  const confirm = screen.getByRole("button", { name: "Confirm and assign invoice number" });
  expect(confirm).toBeDisabled(); // nothing is linked automatically (D-072)
  fireEvent.click(screen.getByRole("button", { name: /Rami Store .* suggested/ }));
  await screen.findByText("Customer linked and the draft repriced.");
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirm and assign invoice number" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm and assign invoice number" }));
  await screen.findByText("Order confirmed; the invoice is now official.");
  await waitFor(() => expect(screen.getByLabelText("Delivery date")).toBeInTheDocument());
  expect(calls.some((c) => c.includes("/orders/o1/link-customer") && c.startsWith("POST"))).toBe(true);
  expect(calls.some((c) => c.includes("/orders/o1/confirm") && c.startsWith("POST"))).toBe(true);
});
