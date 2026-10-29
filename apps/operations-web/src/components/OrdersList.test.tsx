import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OrdersPanel, type OrderSummary } from "./OrdersPanel";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(async () => { cleanup(); vi.unstubAllGlobals(); await i18n.changeLanguage("en"); });

function order(id: string, status: OrderSummary["status"], linked = true): OrderSummary {
  return {
    id, status, contact_name: `Customer ${id}`, contact_phone: "+96170000001", contact_address: "Beirut",
    notes: null, currency: "USD", intended_customer_id: null, intended_assurance: null,
    linked_customer_id: linked ? `customer-${id}` : null, invoice_id: `invoice-${id}`,
    delivery_date: null, decision_note: null, created_at: "2026-09-19T10:00:00Z", decided_at: null,
  };
}

function setup(orders: OrderSummary[], pending = false) {
  const calls: { path: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost");
    const method = init?.method ?? "GET";
    calls.push({ path: url.pathname, method, body: typeof init?.body === "string" ? JSON.parse(init.body) : null });
    if (url.pathname.endsWith("/orders")) return Promise.resolve(Response.json({ orders }));
    const current = orders.find((row) => url.pathname.includes(`/orders/${row.id}`));
    if (current) {
      if (method === "POST" && url.pathname.endsWith("/decline")) current.status = "DECLINED";
      if (method === "POST" && url.pathname.endsWith("/confirm")) current.status = "CONFIRMED";
      return Promise.resolve(Response.json({
        order: current, candidates: [],
        invoice: { id: current.invoice_id, status: current.status === "RECEIVED" ? "DRAFT" : "CONFIRMED", current_revision_id: "latest-revision", official_invoice_number: current.status === "CONFIRMED" ? "2026-000001" : null, net_sales: "1234.50", currency: "USD", items: [] },
        cancellation_requests: pending ? [{ id: "cancel1", order_id: current.id, status: "PENDING", reason: "Changed plans", created_at: current.created_at, decided_at: null, decision_note: null }] : [],
      }));
    }
    if (url.pathname === "/api/v1/delivery-tasks") return Promise.resolve(Response.json({ sole_operator: true, eligible_members: [], tasks: [] }));
    return Promise.resolve(Response.json({}));
  }));
  const view = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><OrdersPanel tenantId="t1" /></MemoryRouter></QueryClientProvider>);
  return { ...view, calls };
}

test("state chips count the entire loaded inbox and filter locally without changing the waiting count", async () => {
  const { calls, container } = setup([order("a", "RECEIVED"), order("b", "RECEIVED"), order("c", "CONFIRMED"), order("d", "DECLINED"), order("e", "CANCELLED")]);
  const inbox = screen.getByRole("list", { name: "Orders" });
  await within(inbox).findByRole("button", { name: /^Customer a/ });
  const chips = screen.getByRole("group", { name: "Order states" });
  expect(container.querySelector(".list-head-count")).toHaveTextContent("5 orders");
  for (const label of ["All 5", "Received 2", "Confirmed 1", "Declined 1", "Cancelled 1"]) {
    expect(within(chips).getByRole("button", { name: label })).toBeInTheDocument();
  }
  for (const [label, names] of [
    ["Received 2", ["a", "b"]], ["Confirmed 1", ["c"]], ["Declined 1", ["d"]], ["Cancelled 1", ["e"]], ["All 5", ["a", "b", "c", "d", "e"]],
  ] as const) {
    fireEvent.click(within(chips).getByRole("button", { name: label }));
    expect(within(chips).getByRole("button", { name: label })).toHaveAttribute("aria-pressed", "true");
    expect(within(inbox).getAllByRole("listitem")).toHaveLength(names.length);
    for (const name of names) expect(within(inbox).getByRole("button", { name: new RegExp(`^Customer ${name}`) })).toBeInTheDocument();
    expect(screen.getByText("2 awaiting review")).toBeInTheDocument();
  }
  expect(calls).toHaveLength(1); // no search, extra list queries or per-row total fetches
  expect(screen.queryByRole("search")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Search" })).not.toBeInTheDocument();
  expect(document.querySelector(".fab")).toBeNull();
});

test("an empty state filter can be cleared without losing loaded orders", async () => {
  setup([order("a", "RECEIVED")]);
  await screen.findByRole("button", { name: /^Customer a/ });
  fireEvent.click(screen.getByRole("button", { name: "Declined 0" }));
  expect(screen.getByText("No orders in this state.")).toBeInTheDocument();
  expect(screen.queryByText("No storefront orders yet.")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "All 1" }));
  expect(screen.getByRole("button", { name: /^Customer a/ })).toBeInTheDocument();
});

test.each([
  ["RECEIVED", false, ["Order review"]],
  ["RECEIVED", true, ["Order review"]],
  ["CONFIRMED", true, ["Order review", "Invoice"]],
  ["CONFIRMED", false, ["Order review"]],
  ["DECLINED", true, ["Order review"]],
  ["CANCELLED", true, ["Order review", "Invoice"]],
  ["CANCELLED", false, ["Order review"]],
] as const)("the %s order menu (invoice: %s) offers exactly review and any linked invoice", async (status, hasInvoice, expected) => {
  setup([{ ...order("a", status), invoice_id: hasInvoice ? "invoice-a" : null }]);
  fireEvent.click(await screen.findByRole("button", { name: "More actions for Customer a" }));
  const menu = screen.getByRole("group", { name: "More actions for Customer a" });
  const controls = within(menu).queryAllByRole("button").concat(within(menu).queryAllByRole("link"));
  expect(controls.map((control) => control.textContent).sort()).toEqual([...expected].sort());
  const invoiceLink = within(menu).queryByRole("link", { name: "Invoice" });
  if (invoiceLink) expect(invoiceLink).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=invoice-a");
  fireEvent.click(within(menu).getByRole("button", { name: "Order review" }));
  expect(await screen.findByRole("article", { name: "Order review" })).toHaveTextContent("Customer a");
});

test("Arabic rows, chips and actions render RTL", async () => {
  await i18n.changeLanguage("ar");
  const current = { ...order("a", "RECEIVED"), contact_name: "متجر بيروت" };
  const { container, calls } = setup([current]);
  const inbox = screen.getByRole("list", { name: "الطلبات" });
  const row = await within(inbox).findByRole("button", { name: /^متجر بيروت/ });
  expect(container.querySelector(".orders-list-page")).toHaveAttribute("dir", "rtl");
  expect(within(inbox).getByText("مستلم")).toBeInTheDocument();
  expect(calls).toHaveLength(1);
  fireEvent.click(row);
  await screen.findByRole("article", { name: "مراجعة الطلب" });
  const chips = screen.getByRole("group", { name: "حالات الطلبات" });
  const all = within(chips).getByRole("button", { name: "الكل 1" });
  all.focus();
  fireEvent.keyDown(all, { key: "ArrowLeft" });
  expect(within(chips).getByRole("button", { name: "مستلم 1" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "إجراءات أخرى لـ متجر بيروت" }));
  expect(within(screen.getByRole("group", { name: "إجراءات أخرى لـ متجر بيروت" })).getByRole("button", { name: "مراجعة الطلب" })).toBeInTheDocument();
});
