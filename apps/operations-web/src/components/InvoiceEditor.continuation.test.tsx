import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { InvoiceEditor } from "./InvoiceEditor";

/**
 * Order workflow fix M3: an official invoice opened from a link (next steps, a delivery, a payment
 * line) is read-only; Payments opened for it selects its open amount through the existing
 * "Choose amounts" allocation and sends exactly the command the owner would send by hand.
 */
const tenantId = "11111111-1111-1111-1111-111111111111";
const customerId = "22222222-2222-2222-2222-222222222222";
const older = { id: "aaaaaaaa-0000-4000-8000-000000000001", number: "2026-000001", target: "cccccccc-0000-4000-8000-000000000001", open: "10.0000" };
const newer = { id: "aaaaaaaa-0000-4000-8000-000000000002", number: "2026-000002", target: "cccccccc-0000-4000-8000-000000000002", open: "22.5000" };

const invoiceBody = (invoice: typeof newer, status = "CONFIRMED") => ({
  id: invoice.id, tenant_id: tenantId, status, official_invoice_number: status === "DRAFT" ? null : invoice.number, confirmed_at: "2026-09-24T08:10:00Z",
  customer_id: customerId, customer_snapshot: { id: customerId, name: "Maya Market", phone: "+96170123456" },
  current_revision_id: "55555555-5555-4555-8555-555555555555", server_revision_number: 1, pricing_version: "pricing-v1", currency: "USD",
  prior_balance: "10.0000", subtotal: invoice.open, discount_total: "0.0000", markup_total: "0.0000", net_sales: invoice.open, total_due: "32.5000",
  items: [], created_at: "2026-09-24T08:00:00Z", updated_at: "2026-09-24T08:10:00Z",
});

let receipts: Array<Record<string, unknown>> = [];
let requested: string[] = [];

function stubApi(invoiceStatus = "CONFIRMED") {
  receipts = [];
  requested = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    const method = init?.method ?? "GET";
    requested.push(`${method} ${url.split("?")[0]}`);
    const reply = (body: unknown, status = 200) => Promise.resolve(Response.json(body, { status }));
    if (url.includes("/customer-ledger/settings")) return reply({ tenant_id: tenantId, customer_overdue_threshold_days: null });
    if (url.includes("/customer-ledger/debts")) return reply({ debts: [] });
    if (url.includes("/balances")) return reply({ customer_id: customerId, customer_name: "Maya Market", balances: [] });
    if (url.includes("/history")) return reply({ revisions: [] });
    if (url.includes(`/payments/customers/${customerId}/obligations`)) {
      return reply({ customer_id: customerId, currency: "USD", obligations: [older, newer].map((row) => ({ target_ledger_entry_id: row.target, source_type: "INVOICE", source_id: row.id, label: `Invoice ${row.number}`, effective_at: "2026-09-24T08:00:00Z", original_amount: row.open, allocated_amount: "0.0000", outstanding_amount: row.open })) });
    }
    if (url.includes("/customer-receipts") && method === "POST") {
      receipts.push(JSON.parse(init?.body as string) as Record<string, unknown>);
      return reply({ id: "p1", direction: "CUSTOMER_RECEIPT", amount: newer.open, currency: "USD", allocated_amount: newer.open, unallocated_amount: "0.0000", customer_balance: older.open, available_credit: "0.0000", allocations: [] }, 201);
    }
    if (url.includes(`/api/v1/tenants/${tenantId}/customers/${customerId}`)) {
      return reply({ id: customerId, tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", address: "Hamra", latitude: null, longitude: null, grade: "A", created_at: "2026-08-27T08:00:00Z", updated_at: "2026-08-27T08:00:00Z" });
    }
    if (url.includes(`/api/v1/invoices/${newer.id}`)) return reply(invoiceBody(newer, invoiceStatus));
    return reply({ detail: { code: "INVOICE_NOT_FOUND", message: "Invoice was not found" } }, 404);
  }));
}

const renderEditor = (invoiceId: string | null, initialView: string | null = null) => render(
  <MemoryRouter>
    <InvoiceEditor initialView={initialView} invoiceId={invoiceId} membershipId="66666666-6666-4666-8666-666666666666" tenantId={tenantId} />
  </MemoryRouter>,
);

beforeEach(async () => {
  sessionStorage.clear();
  await i18n.changeLanguage("en");
  let counter = 0;
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => `bbbbbbbb-bbbb-4bbb-8bbb-${String(++counter).padStart(12, "0")}`) });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("an official invoice opened by link reads as an intentional read-only document", async () => {
  stubApi();
  renderEditor(newer.id);
  expect(await screen.findByRole("heading", { name: newer.number })).toBeInTheDocument();
  expect(screen.getByText(/Opened for viewing, sharing and payments/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Start a new invoice" })).toHaveAttribute("href", `/workspace?tenant=${tenantId}&section=invoices`);
  for (const action of ["Create revision", "Cancel invoice", "Save draft", "Recalculate", "Confirm invoice"]) {
    expect(screen.queryByRole("button", { name: action })).not.toBeInTheDocument();
  }
  expect(screen.queryByRole("group", { name: "Item entry method" })).not.toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Customer and currency" })).getByText("Maya Market")).toBeInTheDocument(); // customer selected
  expect(screen.getByRole("link", { name: "Create delivery" })).toHaveAttribute("href", `/workspace?tenant=${tenantId}&section=deliveries&invoice=${newer.id}`);
});

test("Payments opened for the newer invoice selects its open amount and sends the hand-picked command", async () => {
  stubApi();
  renderEditor(newer.id, "payments");
  const payments = await screen.findByRole("region", { name: "Payments" }).catch(() => screen.getByLabelText("Payments"));
  expect(await within(payments).findByText(`Payment for invoice ${newer.number}: its open amount is selected. Change the amounts if the customer pays a different sum.`)).toBeInTheDocument();
  await waitFor(() => expect(within(payments).getByLabelText(`Allocate to Invoice ${newer.number}`)).toHaveValue(22.5));
  expect(within(payments).getByRole("button", { name: "Choose amounts" })).toHaveAttribute("aria-pressed", "true");
  expect(within(payments).getByLabelText(`Allocate to Invoice ${older.number}`)).toHaveValue(null);
  // M4: an invoice reference on a payment line opens that invoice.
  expect(within(payments).getByRole("link", { name: `Invoice ${older.number}` })).toHaveAttribute("href", `/workspace?tenant=${tenantId}&section=invoices&invoice=${older.id}`);
  expect(within(payments).getByLabelText("Amount received")).toHaveValue(22.5);
  fireEvent.click(within(payments).getByRole("button", { name: "Record receipt" }));
  await waitFor(() => expect(receipts, `${requested.join(" | ")} || ${screen.queryByRole("alert")?.textContent ?? ""}`).toHaveLength(1));
  const prefilled = receipts[0]!;
  expect(prefilled.allocations).toEqual([{ target_ledger_entry_id: newer.target, amount: newer.open }]);
  expect(prefilled.amount).toBe(newer.open);

  // The standalone path: the same invoice's Payments view, "Choose amounts" and the amounts typed by hand.
  cleanup();
  stubApi();
  renderEditor(newer.id);
  await screen.findByRole("heading", { name: newer.number });
  fireEvent.click(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Payments" }));
  const standalone = screen.getByLabelText("Payments");
  fireEvent.click(await within(standalone).findByRole("button", { name: "Choose amounts" }));
  fireEvent.change(await within(standalone).findByLabelText(`Allocate to Invoice ${newer.number}`), { target: { value: newer.open } });
  fireEvent.change(within(standalone).getByLabelText("Amount received"), { target: { value: newer.open } });
  fireEvent.click(within(standalone).getByRole("button", { name: "Record receipt" }));
  await waitFor(() => expect(receipts).toHaveLength(1));
  const byHand = receipts[0]!;
  const comparable = (body: Record<string, unknown>) => ({ ...body, idempotency_key: "-", paid_at: "-" });
  expect(comparable(prefilled)).toEqual(comparable(byHand));
});

test("an unknown, foreign or draft invoice in the link is ignored safely", async () => {
  stubApi();
  renderEditor("99999999-9999-4999-8999-999999999999", "payments");
  await waitFor(() => expect(requested.some((row) => row.includes("/api/v1/invoices/99999999"))).toBe(true));
  expect(screen.queryByText(/Opened for viewing/)).not.toBeInTheDocument();
  expect(requested.some((row) => row.includes(`/tenants/${tenantId}/customers/`))).toBe(false);
  expect(screen.getByText("No customer chosen yet")).toBeInTheDocument();

  cleanup();
  stubApi("DRAFT");
  renderEditor(newer.id);
  await waitFor(() => expect(requested.some((row) => row.includes(`/api/v1/invoices/${newer.id}`))).toBe(true));
  expect(screen.queryByText(/Opened for viewing/)).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: newer.number })).not.toBeInTheDocument();
});
