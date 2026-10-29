import "fake-indexeddb/auto";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { deleteLocalDatabase, openLocalDatabase } from "../offline/db";
import { InvoiceEditor } from "./InvoiceEditor";

/**
 * OE-07: the editor's layout (cards in reading order, the bottom action bar, per-line "More") and
 * the customer picker's search while typing. Every button keeps its handler and disabled rule.
 */
const tenantId = "11111111-1111-1111-1111-111111111111";
const membershipId = "66666666-6666-4666-8666-666666666666";
const customerId = "22222222-2222-2222-2222-222222222222";
const invoiceId = "44444444-4444-4444-4444-444444444444";
const customerRow = { id: customerId, tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", address: "Hamra", latitude: null, longitude: null, grade: "A", created_at: "2026-08-27T08:00:00Z", updated_at: "2026-08-27T08:00:00Z" };

function line(overrides: Record<string, unknown> = {}) {
  return { id: "item-1", line_number: 1, product_id: null, product_name: "Water crate", barcode: null, media_snapshot: {}, quantity: "2.0000", price_basis: "PIECE", pieces_per_box: null, normal_unit_price: "5.0000", effective_unit_price: "5.0000", customer_grade: "A", price_source: "NORMAL_PRICE", grade_discount_percent: null, line_discount: "0.0000", line_markup: "0.0000", line_total: "10.0000", supplier_id: null, product_cost_entry_id: null, unit_cost: null, cost_currency: null, cost_basis: null, cost_pieces_per_box: null, cost_source_type: null, is_cost_override: false, cost_override_reason: null, ...overrides };
}

function invoice(overrides: Record<string, unknown> = {}) {
  return { id: invoiceId, tenant_id: tenantId, status: "DRAFT", official_invoice_number: null, confirmed_at: null, customer_id: customerId, customer_snapshot: { id: customerId, name: "Maya Market", phone: "+96170123456" }, current_revision_id: "rev-1", server_revision_number: 1, pricing_version: "pricing-v1", currency: "USD", prior_balance: "3.0000", subtotal: "10.0000", discount_total: "0.0000", markup_total: "0.0000", net_sales: "10.0000", total_due: "13.0000", items: [line()], created_at: "2026-09-23T08:00:00Z", updated_at: "2026-09-23T08:00:00Z", ...overrides };
}

let requests: Array<{ method: string; url: string }> = [];

/** The editor's calls; `routes` answers first. Unknown calls fail like a missing route would. */
function stubApi(routes: (url: string, method: string) => Response | Promise<Response> | undefined = () => undefined) {
  requests = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    const method = init?.method ?? "GET";
    requests.push({ method, url });
    const answer = routes(url, method);
    if (answer) return Promise.resolve(answer);
    if (url.includes("/customer-ledger/settings")) return Promise.resolve(Response.json({ tenant_id: tenantId, customer_overdue_threshold_days: null }));
    if (url.includes("/customer-ledger/debts")) return Promise.resolve(Response.json({ debts: [] }));
    if (url.includes("/customers/search")) return Promise.resolve(Response.json({ customers: [customerRow] }));
    if (url.includes(`/tenants/${tenantId}/customers?q=`)) return Promise.resolve(Response.json({ page: 1, limit: 10, total: 1, total_pages: 1, customers: [{ ...customerRow, balances: [{ currency: "USD", balance: "12.5000" }] }] }));
    if (url.includes(`/tenants/${tenantId}/customers/${customerId}`)) return Promise.resolve(Response.json(customerRow));
    if (url.includes("/balances")) return Promise.resolve(Response.json({ customer_id: customerId, customer_name: "Maya Market", balances: [] }));
    if (url.includes("/obligations")) return Promise.resolve(Response.json({ customer_id: customerId, currency: "USD", obligations: [] }));
    if (url.includes("/history")) return Promise.resolve(Response.json({ revisions: [] }));
    if (url.includes("/suppliers")) return Promise.resolve(Response.json({ suppliers: [] }));
    if (url.includes("/capabilities")) return Promise.resolve(Response.json([]));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));
}

const typedSearches = () => requests.filter((row) => row.url.includes("/customers?q="));
const renderEditor = (props: { invoiceId?: string } = {}) => render(<MemoryRouter><InvoiceEditor membershipId={membershipId} tenantId={tenantId} {...props} /></MemoryRouter>);

beforeEach(async () => {
  sessionStorage.clear();
  await i18n.changeLanguage("en");
  let counter = 0;
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => `bbbbbbbb-bbbb-4bbb-8bbb-${String(++counter).padStart(12, "0")}`) });
});

afterEach(async () => {
  cleanup();
  vi.unstubAllGlobals();
  await i18n.changeLanguage("en");
  document.documentElement.dir = "ltr";
});

test("typing two or more characters shows matching customers by name, after a short pause, with what they owe", async () => {
  stubApi();
  renderEditor();
  const field = screen.getByLabelText("Phone");
  expect(field).toHaveAccessibleDescription(/Type a name or part of the phone/);
  fireEvent.change(field, { target: { value: "m" } });
  await new Promise((resolve) => setTimeout(resolve, 400));
  expect(typedSearches()).toHaveLength(0); // one character asks nothing
  fireEvent.change(field, { target: { value: "ma" } });
  fireEvent.change(field, { target: { value: "may" } });
  const match = await screen.findByRole("button", { name: /Maya Market/ });
  expect(typedSearches().map((row) => row.url.split("/api/v1")[1])).toEqual([`/tenants/${tenantId}/customers?q=may&limit=10`]); // only the latest text
  expect(within(match).getByText("+96170123456")).toHaveAttribute("dir", "ltr");
  expect(within(match).getByText("+96170123456").tagName).toBe("BDI");
  expect(match).toHaveTextContent("Owes 12.5000 USD");
  expect(screen.getByText("1 customer matches what you typed.")).toBeInTheDocument();
  fireEvent.click(match);
  expect(within(screen.getByRole("region", { name: "Customer and currency" })).getByText("Maya Market")).toBeInTheDocument();
});

test("a full phone and Enter still runs the exact-phone search, and no typed lookup overrides it", async () => {
  stubApi();
  renderEditor();
  const field = screen.getByLabelText("Phone");
  fireEvent.change(field, { target: { value: "+96170123456" } });
  fireEvent.submit(field.closest("form")!);
  expect(await screen.findByRole("button", { name: /Maya Market/ })).not.toHaveTextContent("Owes");
  expect(requests.filter((row) => row.url.includes("/customers/search")).map((row) => row.url.split("/api/v1")[1])).toEqual([`/tenants/${tenantId}/customers/search?phone=%2B96170123456`]);
  expect(screen.getByText("1 matching customer record found.")).toBeInTheDocument();
  await new Promise((resolve) => setTimeout(resolve, 400));
  expect(typedSearches()).toHaveLength(0);
});

test("offline, a typed Arabic name finds the customer on this device with the server's folding", async () => {
  await openLocalDatabase(tenantId, membershipId).customers.put({ id: "c-local".padEnd(36, "0"), tenant_id: tenantId, name: "أحمد للتجارة", phone: "+96170111222", phone_raw: null, address: null, latitude: null, longitude: null, grade: "B", version: 1, created_at: "2026-09-18T00:00:00Z", updated_at: "2026-09-18T00:00:00Z" });
  stubApi((url) => (url.includes("/customers?q=") ? (() => { throw new TypeError("Failed to fetch"); })() : undefined));
  renderEditor();
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "احمد" } });
  const match = await screen.findByRole("button", { name: /أحمد للتجارة/ });
  expect(within(match).getByText("+96170111222")).toHaveAttribute("dir", "ltr");
  expect(screen.getByText("1 customer on this device matches (offline).")).toBeInTheDocument();
  await deleteLocalDatabase(tenantId, membershipId);
});

test("each line keeps quantity, unit and line total in view and folds discount, markup and cost behind More", async () => {
  stubApi();
  renderEditor();
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  fireEvent.click(within(screen.getByRole("group", { name: "Item entry method" })).getByRole("button", { name: "Manual item" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Item name" }), { target: { value: "Ice" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Unit price" }), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "Add manual line" }));

  const lines = screen.getByRole("region", { name: "Invoice lines" });
  expect(within(lines).getByLabelText("Quantity / calculator")).toBeVisible();
  expect(within(lines).getByLabelText("Price basis")).toBeVisible();
  expect(within(lines).getByText("Line total")).toBeVisible();
  const more = within(lines).getByRole("button", { name: "More: discount, markup, cost (Ice)" });
  expect(more).toHaveAttribute("aria-expanded", "false");
  expect(within(lines).getByLabelText("Line discount")).not.toBeVisible();
  fireEvent.click(more);
  expect(more).toHaveAttribute("aria-expanded", "true");
  expect(within(lines).getByLabelText("Line discount")).toBeVisible();
  fireEvent.click(more);
  expect(within(lines).getByLabelText("Line markup")).not.toBeVisible();
  // A value other than the default opens it by itself.
  fireEvent.change(within(lines).getByLabelText("Line markup"), { target: { value: "0.5" } });
  expect(more).toHaveAttribute("aria-expanded", "true");
  expect(within(lines).getByLabelText("Line markup")).toBeVisible();
});

test("a line opened by link with a discount or a cost override shows More already open; a plain line stays folded", async () => {
  stubApi((url, method) => (url.includes(`/api/v1/invoices/${invoiceId}?`) && method === "GET"
    ? Response.json(invoice({ items: [line(), line({ id: "item-2", line_number: 2, product_name: "Ice bag", line_discount: "0.5000", line_total: "4.5000" })], subtotal: "15.0000", net_sales: "14.5000" }))
    : undefined));
  renderEditor({ invoiceId });
  const lines = await screen.findByRole("region", { name: "Invoice lines" });
  await within(lines).findByText("Ice bag");
  expect(within(lines).getByRole("button", { name: /\(Water crate\)/ })).toHaveAttribute("aria-expanded", "false");
  expect(within(lines).getByRole("button", { name: /\(Ice bag\)/ })).toHaveAttribute("aria-expanded", "true");
  expect(within(lines).getAllByLabelText("Line discount")[1]).toHaveValue("0.5");
  // The saved revision is what the lines show: each line's own server total.
  expect(within(lines).getByText("10.0000 USD")).toBeVisible();
  expect(within(lines).getByText("4.5000 USD")).toBeVisible();
});

test("the action bar holds the editor's only Save and Confirm, with their handlers and disabled rules", async () => {
  const saves: string[] = [];
  const confirms: string[] = [];
  stubApi((url, method) => {
    if (url.endsWith(`/api/v1/invoices?tenant_id=${tenantId}`) && method === "POST") { saves.push(url); return Response.json(invoice(), { status: 201 }); }
    if (url.includes("/confirm") && method === "POST") { confirms.push(url); return Response.json(invoice({ status: "CONFIRMED", official_invoice_number: "2026-000007", confirmed_at: "2026-09-23T08:10:00Z" })); }
    return undefined;
  });
  const print = vi.fn();
  vi.stubGlobal("print", print);
  renderEditor();
  const bar = () => screen.getByRole("group", { name: "Invoice actions" });
  expect(screen.getAllByRole("group", { name: "Invoice actions" })).toHaveLength(1);
  expect(within(bar()).getByRole("button", { name: "Calculate and save draft" })).toBeDisabled(); // no customer, no line
  expect(within(bar()).getByText("—")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Search" })[0]!);
  fireEvent.click(await screen.findByRole("button", { name: /Maya Market/ }));
  expect(within(bar()).getByRole("button", { name: "Calculate and save draft" })).toBeDisabled(); // still no line
  fireEvent.click(within(screen.getByRole("group", { name: "Item entry method" })).getByRole("button", { name: "Manual item" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Item name" }), { target: { value: "Water crate" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Unit price" }), { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Add manual line" }));
  const save = within(bar()).getByRole("button", { name: "Calculate and save draft" });
  expect(screen.getAllByRole("button", { name: "Calculate and save draft" })).toEqual([save]);
  expect(save).toBeEnabled();
  fireEvent.click(save);

  const confirm = await within(bar()).findByRole("button", { name: "Confirm and assign invoice number" });
  expect(saves).toHaveLength(1);
  expect(within(bar()).getByText("Invoice total (USD)")).toBeInTheDocument();
  expect(within(bar()).getByText("10.0000")).toBeInTheDocument(); // the saved revision's total
  expect(screen.getAllByRole("button", { name: "Confirm and assign invoice number" })).toEqual([confirm]);
  expect(confirm).toBeEnabled();
  // A change after saving: the same Confirm turns off and says why, inside the bar.
  fireEvent.change(screen.getByLabelText("Quantity / calculator"), { target: { value: "3" } });
  expect(confirm).toBeDisabled();
  expect(confirm).toHaveAccessibleDescription("You changed this invoice after saving. Save it first, then confirm.");
  expect(within(bar()).getByRole("note")).toHaveTextContent("Save it first, then confirm.");
  fireEvent.click(confirm);
  expect(confirms).toHaveLength(0);
  fireEvent.change(screen.getByLabelText("Quantity / calculator"), { target: { value: "1" } });
  await waitFor(() => expect(confirm).toBeEnabled());
  fireEvent.click(confirm);

  // The confirmed document carries its own bar: the total and Print.
  const document_ = await screen.findByRole("article", { name: "2026-000007" });
  expect(confirms).toHaveLength(1);
  const documentBar = within(document_).getByRole("group", { name: "Invoice actions" });
  fireEvent.click(within(documentBar).getByRole("button", { name: "Print" }));
  expect(print).toHaveBeenCalledTimes(1);
  expect(screen.getAllByRole("button", { name: "Print" })).toHaveLength(1);
});

test("a single revision folds its history behind the title; more than one lists every entry", async () => {
  const revision = (number: number, current: boolean) => ({ ...invoice({ status: "CONFIRMED", official_invoice_number: "2026-000007", confirmed_at: "2026-09-23T08:10:00Z", current_revision_id: `rev-${number}`, server_revision_number: number }), predecessor_revision_id: null, reason: null, revision_created_at: "2026-09-23T08:10:00Z", is_current: current, ledger_delta: null });
  let revisions = [revision(1, true)];
  stubApi((url, method) => {
    if (url.includes(`/api/v1/invoices/${invoiceId}?`) && method === "GET") return Response.json(invoice({ status: "CONFIRMED", official_invoice_number: "2026-000007", confirmed_at: "2026-09-23T08:10:00Z" }));
    if (url.includes("/history")) return Response.json({ revisions });
    return undefined;
  });
  renderEditor({ invoiceId });
  const history = await screen.findByRole("region", { name: "Immutable revision history" });
  const fold = history.querySelector("details.invoice-history-fold")!;
  expect(fold).not.toHaveAttribute("open");
  expect(within(history).getByText("R1")).not.toBeVisible();
  fireEvent.click(fold.querySelector("summary")!);
  expect(within(history).getByText("R1")).toBeVisible();

  cleanup();
  revisions = [revision(1, false), revision(2, true)];
  renderEditor({ invoiceId });
  const listed = await screen.findByRole("region", { name: "Immutable revision history" });
  await within(listed).findByText("R2");
  expect(listed.querySelector(".invoice-history-fold")).toBeNull();
  expect(within(listed).getByText("R1")).toBeVisible();
});

test("in Arabic the editor reads right to left with the same controls, and phones stay left to right", async () => {
  await i18n.changeLanguage("ar");
  document.documentElement.dir = "rtl";
  stubApi();
  renderEditor();
  expect(screen.getByRole("heading", { name: "ابحث عن العميل بالاسم أو الهاتف" })).toBeInTheDocument();
  const field = screen.getByLabelText("الهاتف");
  expect(field).toHaveAttribute("dir", "auto");
  expect(field).toHaveAccessibleDescription(/اكتب اسماً أو جزءاً من رقم الهاتف/);
  const bar = screen.getByRole("group", { name: "إجراءات الفاتورة" });
  expect(within(bar).getByText("إجمالي الفاتورة")).toBeInTheDocument();
  fireEvent.change(field, { target: { value: "ما" } });
  const match = await screen.findByRole("button", { name: /Maya Market/ });
  expect(within(match).getByText("+96170123456")).toHaveAttribute("dir", "ltr");
  expect(match).toHaveTextContent("عليه");
  expect(screen.getByText("عميل واحد يطابق ما كتبته.")).toBeInTheDocument();
});
