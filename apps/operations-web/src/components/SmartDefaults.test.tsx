import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { DeliveryPanel } from "./DeliveryPanel";
import { InvoiceEditor } from "./InvoiceEditor";

const tenantId = "44444444-4444-4444-4444-444444444444";
const customer = { id: "66666666-6666-6666-6666-666666666666", tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", address: "Hamra", latitude: null, longitude: null, grade: "A", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" };

beforeEach(async () => { await i18n.changeLanguage("en"); localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function stubInvoiceApi(receipts: Array<Record<string, unknown>> = []) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/customer-receipts") && init?.method === "POST") {
      receipts.push(JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>);
      return Promise.resolve(Response.json({ id: "pay1", direction: "CUSTOMER_RECEIPT", amount: "5.0000", currency: "LBP", allocated_amount: "0", unallocated_amount: "5.0000", customer_balance: "0", available_credit: "5.0000" }, { status: 201 }));
    }
    if (url.includes("/customer-ledger/settings")) return Promise.resolve(Response.json({ tenant_id: tenantId, customer_overdue_threshold_days: null }));
    if (url.includes("/customer-ledger/debts")) return Promise.resolve(Response.json({ debts: [] }));
    if (url.includes("/customers/search")) return Promise.resolve(Response.json({ customers: [customer] }));
    if (url.includes("/balances")) return Promise.resolve(Response.json({ customer_id: customer.id, customer_name: customer.name, balances: [] }));
    if (url.includes("/obligations")) return Promise.resolve(Response.json({ customer_id: customer.id, currency: "LBP", obligations: [] }));
    if (url.includes("/api/v1/suppliers?")) return Promise.resolve(Response.json({ suppliers: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));
}

test("a new invoice starts at the phone in the currency used last, then moves to item entry once the customer is chosen", async () => {
  localStorage.setItem(`tawzeevo.last.currency.${tenantId}`, "LBP");
  stubInvoiceApi();
  render(<MemoryRouter><InvoiceEditor membershipId="m1" tenantId={tenantId} /></MemoryRouter>);
  const phone = screen.getByLabelText("Phone");
  await waitFor(() => expect(phone).toHaveFocus());
  expect(within(screen.getByRole("region", { name: "Customer and currency" })).getByRole("textbox")).toHaveValue("LBP");
  fireEvent.change(phone, { target: { value: "+96170123456" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Barcode" })).toHaveFocus());
});

test("payment method is picked from a list and sent as before", async () => {
  const receipts: Array<Record<string, unknown>> = [];
  stubInvoiceApi(receipts);
  render(<MemoryRouter><InvoiceEditor membershipId="m1" tenantId={tenantId} /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170123456" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  fireEvent.click(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Payments" }));
  const receiptForm = screen.getByLabelText("Amount received").closest("form")!;
  const method = within(receiptForm).getByLabelText("Method");
  expect(within(method).getAllByRole("option").map((option) => option.textContent)).toEqual(["Cash", "Card", "Bank transfer", "Cheque", "Other"]);
  expect(method).toHaveValue("CASH");
  fireEvent.change(method, { target: { value: "TRANSFER" } });
  fireEvent.change(within(receiptForm).getByLabelText("Amount received"), { target: { value: "5" } });
  fireEvent.click(within(receiptForm).getByRole("button", { name: "Record receipt" }));
  await waitFor(() => expect(receipts[0]).toMatchObject({ method: "TRANSFER", amount: "5" }));
});

test("choosing an invoice to deliver brings its delivery date with it", async () => {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    if (path.endsWith("/eligible-invoices")) return Promise.resolve(Response.json({ invoices: [{ invoice_id: "inv1", official_invoice_number: "2026-000001", customer_id: "c1", customer_name: "Corner Shop", currency: "USD", net_sales: "30.0000", confirmed_at: "2026-09-19T05:00:00Z", order_id: "o1", delivery_date: "2026-09-30" }] }));
    if (path.endsWith("/delivery-tasks")) return Promise.resolve(Response.json({ tasks: [], eligible_members: [], sole_operator: true }));
    if (path.endsWith("/memberships")) return Promise.resolve(Response.json({ members: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
  render(<MemoryRouter><DeliveryPanel tenantId="t1" /></MemoryRouter>);
  await screen.findByRole("option", { name: /2026-000001/ });
  fireEvent.change(screen.getByLabelText("Confirmed invoice"), { target: { value: "inv1" } });
  expect(screen.getByLabelText("Delivery date")).toHaveValue("2026-09-30");
});
