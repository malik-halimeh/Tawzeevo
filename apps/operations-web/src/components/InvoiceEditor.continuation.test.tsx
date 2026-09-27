import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { InvoiceEditor } from "./InvoiceEditor";

/**
 * An invoice opened from a link (a customer's invoices, next steps, a delivery, a payment line)
 * loads its lines rebuilt from the current revision (D-101): a draft is editable, a confirmed invoice
 * can be revised or cancelled. Payments opened for it selects its open amount through the existing
 * "Choose amounts" allocation and sends exactly the command the owner would send by hand (M3).
 */
const tenantId = "11111111-1111-1111-1111-111111111111";
const customerId = "22222222-2222-2222-2222-222222222222";
const older = { id: "aaaaaaaa-0000-4000-8000-000000000001", number: "2026-000001", target: "cccccccc-0000-4000-8000-000000000001", open: "10.0000" };
const newer = { id: "aaaaaaaa-0000-4000-8000-000000000002", number: "2026-000002", target: "cccccccc-0000-4000-8000-000000000002", open: "22.5000" };
const productId = "dddddddd-0000-4000-8000-000000000001";
const supplierId = "eeeeeeee-0000-4000-8000-000000000001";

const invoiceBody = (invoice: typeof newer, status = "CONFIRMED") => ({
  id: invoice.id, tenant_id: tenantId, status, official_invoice_number: status === "DRAFT" ? null : invoice.number, confirmed_at: "2026-09-24T08:10:00Z",
  customer_id: customerId, customer_snapshot: { id: customerId, name: "Maya Market", phone: "+96170123456" },
  current_revision_id: "55555555-5555-4555-8555-555555555555", server_revision_number: 1, pricing_version: "pricing-v1", currency: "USD",
  prior_balance: "10.0000", subtotal: invoice.open, discount_total: "1.5000", markup_total: "0.2500", net_sales: invoice.open, total_due: "32.5000",
  items: [
    { id: "i1", line_number: 1, product_id: productId, product_name: "Cedar Water", barcode: "5280000000012", media_snapshot: {}, quantity: "2.0000", price_basis: "PIECE", pieces_per_box: 12,
      normal_unit_price: "10.0000", effective_unit_price: "10.0000", customer_grade: "A", price_source: "NORMAL_PRICE", grade_discount_percent: null, line_discount: "0.5000", line_markup: "0.2500", line_total: "19.7500",
      supplier_id: supplierId, product_cost_entry_id: null, unit_cost: "7.2500", cost_currency: "USD", cost_basis: "PIECE", cost_pieces_per_box: 12, cost_source_type: "OWNER_OVERRIDE", is_cost_override: true, cost_override_reason: "Old stock" },
    { id: "i2", line_number: 2, product_id: null, product_name: "Delivery tray", barcode: null, media_snapshot: {}, quantity: "3.0000", price_basis: "PIECE", pieces_per_box: null,
      normal_unit_price: "2.0000", effective_unit_price: "2.0000", customer_grade: null, price_source: "NORMAL_PRICE", grade_discount_percent: null, line_discount: "0.0000", line_markup: "0.0000", line_total: "6.0000",
      supplier_id: null, product_cost_entry_id: null, unit_cost: null, cost_currency: null, cost_basis: null, cost_pieces_per_box: null, cost_source_type: null, is_cost_override: false, cost_override_reason: null },
  ],
  created_at: "2026-09-24T08:00:00Z", updated_at: "2026-09-24T08:10:00Z",
});

let receipts: Array<Record<string, unknown>> = [];
let requested: string[] = [];
let sent: Array<{ method: string; path: string; body: Record<string, unknown> }> = [];

function stubApi(invoiceStatus = "CONFIRMED") {
  receipts = [];
  requested = [];
  sent = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    const method = init?.method ?? "GET";
    requested.push(`${method} ${url.split("?")[0]}`);
    if (method !== "GET" && typeof init?.body === "string") sent.push({ method, path: url.split("?")[0]!, body: JSON.parse(init.body) as Record<string, unknown> });
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
    if (url.includes(`/products/${productId}/cost-options`)) return reply({ product_id: productId, currency: "USD", basis: "PIECE", options: [{ supplier_id: "ffffffff-0000-4000-8000-000000000009", supplier_name: "Preferred Co", is_preferred: true, entry_id: null, unit_cost: "8.0000", cost_basis: "PIECE", pieces_per_box: null, effective_at: null, source_type: null }, { supplier_id: supplierId, supplier_name: "Saved Supplier", is_preferred: false, entry_id: null, unit_cost: "7.5000", cost_basis: "PIECE", pieces_per_box: null, effective_at: null, source_type: null }] });
    if (url.includes("/api/v1/suppliers")) return reply({ suppliers: [] });
    if (url.includes(`/api/v1/invoices/${newer.id}/cancel`) && method === "POST") return reply({ ...invoiceBody(newer, "CANCELLED"), cancelled_at: "2026-09-25T00:00:00Z" });
    if (url.includes(`/api/v1/invoices/${newer.id}/confirm`) && method === "POST") return reply({ ...invoiceBody(newer, "CONFIRMED"), current_revision_id: "77777777-7777-4777-8777-777777777777", server_revision_number: 2 });
    if (url.includes(`/api/v1/invoices/${newer.id}`) && method === "PUT") return reply({ ...invoiceBody(newer, invoiceStatus), current_revision_id: "77777777-7777-4777-8777-777777777777", server_revision_number: 2 });
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

// The lines a save sends after the invoice was opened by link: rebuilt from the revision (D-101).
const rebuiltItems = [
  { product_id: productId, manual_name: null, barcode: "5280000000012", quantity_expression: "2", price_basis: "PIECE", pieces_per_box: 12, manual_unit_price: null,
    line_discount_expression: "0.5", line_markup_expression: "0.25", supplier_id: supplierId, cost_override: "7.25", cost_basis: "PIECE", cost_pieces_per_box: 12, cost_override_reason: "Old stock", accepted_fuzzy_match: null },
  { product_id: null, manual_name: "Delivery tray", barcode: null, quantity_expression: "3", price_basis: "PIECE", pieces_per_box: null, manual_unit_price: "2",
    line_discount_expression: "0", line_markup_expression: "0", supplier_id: null, cost_override: null, cost_basis: null, cost_pieces_per_box: null, cost_override_reason: null, accepted_fuzzy_match: null },
];

test("a confirmed invoice opened by link can be revised with its rebuilt lines, and cancelled (D-101)", async () => {
  stubApi();
  renderEditor(newer.id);
  expect(await screen.findByRole("heading", { name: newer.number })).toBeInTheDocument();
  expect(screen.queryByText(/Opened for viewing/)).not.toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Customer and currency" })).getByText("Maya Market")).toBeInTheDocument(); // customer selected
  expect(screen.getByRole("link", { name: "Create delivery" })).toHaveAttribute("href", `/workspace?tenant=${tenantId}&section=deliveries&invoice=${newer.id}`);
  expect(screen.getByRole("button", { name: "Cancel invoice" })).toBeInTheDocument();

  // Create revision: the editor holds the saved lines and saves them against the current revision.
  fireEvent.click(screen.getByRole("button", { name: "Create revision" }));
  await waitFor(() => expect(requested.filter((row) => row.includes("/cost-options"))).toHaveLength(1));
  fireEvent.click(await screen.findByRole("button", { name: "Save an auditable revision" }));
  await waitFor(() => expect(sent.some((row) => row.method === "PUT")).toBe(true));
  const put = sent.find((row) => row.method === "PUT")!;
  expect(put.path.endsWith(`/api/v1/invoices/${newer.id}`)).toBe(true);
  expect(put.body).toMatchObject({ expected_predecessor_revision_id: "55555555-5555-4555-8555-555555555555", customer_id: customerId, currency: "USD", invoice_discount_expression: "1", invoice_markup_expression: "0", items: rebuiltItems });

  // Cancel from the document, with a reason and the second confirmation.
  cleanup();
  stubApi();
  renderEditor(newer.id);
  await screen.findByRole("heading", { name: newer.number });
  fireEvent.change(screen.getByLabelText("Cancellation reason"), { target: { value: "Customer returned all" } });
  fireEvent.click(screen.getByRole("button", { name: "Cancel invoice" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, cancel invoice" }));
  await waitFor(() => expect(sent.some((row) => row.path.endsWith("/cancel"))).toBe(true));
  expect(sent.find((row) => row.path.endsWith("/cancel"))!.body).toMatchObject({ reason: "Customer returned all" });
});

test("a draft opened by link is editable: its save sends the rebuilt lines, then it can be confirmed (D-101)", async () => {
  stubApi("DRAFT");
  renderEditor(newer.id);
  // The editor (not a document) with both saved lines.
  expect(await screen.findByDisplayValue("Old stock")).toBeInTheDocument();
  expect(screen.getAllByText("Delivery tray").length).toBeGreaterThan(0);
  expect(screen.queryByRole("heading", { name: newer.number })).not.toBeInTheDocument();
  await waitFor(() => expect(requested.filter((row) => row.includes("/cost-options"))).toHaveLength(1));
  fireEvent.click(screen.getByRole("button", { name: "Save a new draft revision" }));
  await waitFor(() => expect(sent.some((row) => row.method === "PUT")).toBe(true));
  expect(sent.find((row) => row.method === "PUT")!.body).toMatchObject({ expected_predecessor_revision_id: "55555555-5555-4555-8555-555555555555", invoice_discount_expression: "1", invoice_markup_expression: "0", items: rebuiltItems });
  fireEvent.click(await screen.findByRole("button", { name: "Confirm and assign invoice number" }));
  await waitFor(() => expect(sent.some((row) => row.path.endsWith("/confirm"))).toBe(true));
  expect(sent.find((row) => row.path.endsWith("/confirm"))!.body).toEqual({ expected_revision_id: "77777777-7777-4777-8777-777777777777" });
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

test("an unknown or foreign invoice in the link is ignored safely", async () => {
  stubApi();
  renderEditor("99999999-9999-4999-8999-999999999999", "payments");
  await waitFor(() => expect(requested.some((row) => row.includes("/api/v1/invoices/99999999"))).toBe(true));
  expect(requested.some((row) => row.includes(`/tenants/${tenantId}/customers/`))).toBe(false);
  expect(screen.getByText("No customer chosen yet")).toBeInTheDocument();
});
