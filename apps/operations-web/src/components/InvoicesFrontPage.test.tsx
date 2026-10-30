import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError } from "../api/client";
import type { BusinessInvoiceListResponse, BusinessInvoiceListRow, InvoiceSummaryResponse } from "../api/types";
import i18n from "../i18n";
import { InvoicesFrontPage } from "./InvoicesFrontPage";
import { PENDING_ORDERS_KEY } from "./pendingOrders";

const summary: InvoiceSummaryResponse = { currencies: [
  { currency: "USD", outstanding_total: "125.0000", overdue_total: "25.0000", open_count: 3, overdue_count: 1, paid_count: 2, draft_count: 1 },
  { currency: "LBP", outstanding_total: "900000.0000", overdue_total: "100000.0000", open_count: 4, overdue_count: 2, paid_count: 1, draft_count: 0 },
] };
const invoice = (id: string, changes: Partial<BusinessInvoiceListRow> = {}): BusinessInvoiceListRow => ({
  id, status: "CONFIRMED", official_invoice_number: `2026-${id}`, confirmed_at: "2026-10-04T10:00:00Z", created_at: "2026-09-30T10:00:00Z",
  currency: "USD", net_sales: "50.0000", total_due: "50.0000", server_revision_number: 1, customer_id: `c-${id}`, customer_name: `Customer ${id}`,
  outstanding: "50.0000", paid_state: "UNPAID", is_overdue: false, overdue_age_days: null, ...changes,
});
const page = (invoices: BusinessInvoiceListRow[], changes: Partial<BusinessInvoiceListResponse> = {}): BusinessInvoiceListResponse => ({ page: 1, limit: 20, total: invoices.length, total_pages: 1, invoices, ...changes });

function Address() {
  const location = useLocation();
  return <output data-testid="address">{location.pathname}{location.search}</output>;
}

function setup({ rows = [invoice("1")], respond, failure, waiting = false, tenantId = "t1" }: {
  rows?: BusinessInvoiceListRow[];
  respond?: (url: URL) => BusinessInvoiceListResponse | Promise<BusinessInvoiceListResponse>;
  failure?: Error | undefined;
  waiting?: boolean;
  tenantId?: string;
} = {}) {
  const calls: URL[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    calls.push(url);
    if (url.pathname === "/api/v1/invoices/summary") {
      if (failure && !(failure instanceof ApiError)) throw failure;
      return Response.json(summary);
    }
    if (url.pathname === "/api/v1/invoices/all") {
      if (failure) {
        if (failure instanceof ApiError) return Response.json({ detail: { code: failure.code, message: failure.message } }, { status: failure.status });
        throw failure;
      }
      return Response.json(respond ? await respond(url) : page(rows));
    }
    // OwnerTodayStrip is mounted unchanged, with its ordinary empty projections.
    if (url.pathname === "/api/v1/delivery-tasks") return Response.json({ tasks: [] });
    if (url.pathname.includes("pickup")) return Response.json({ reports: [] });
    if (url.pathname.includes("collection")) return Response.json({ reports: [] });
    throw new Error(`Unexpected request: ${url}`);
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (waiting) client.setQueryData([PENDING_ORDERS_KEY, tenantId], [{ id: "order1" }]);
  const tree = (id: string) => <QueryClientProvider client={client}><MemoryRouter initialEntries={["/workspace?section=invoices&view=list"]}><InvoicesFrontPage key={id} tenantId={id} /><Address /></MemoryRouter></QueryClientProvider>;
  const view = render(tree(tenantId));
  return { calls, client, view, tree };
}

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test("summary displays separate currencies, server totals and counts; its two actions select chip and currency", async () => {
  const { calls } = setup({ waiting: true });
  const overview = await screen.findByRole("group", { name: "Money overview" });
  const usd = await within(overview).findByRole("region", { name: "USD" });
  const lbp = within(overview).getByRole("region", { name: "LBP" });
  expect(usd).toHaveTextContent("125.00 $");
  expect(usd).toHaveTextContent("3 open invoices");
  expect(usd).toHaveTextContent("25.00 $");
  expect(lbp).toHaveTextContent("900,000 LBP");
  expect(lbp).toHaveTextContent("100,000 LBP");
  expect(lbp).not.toHaveTextContent("USD");
  expect(overview).not.toHaveTextContent("900125");
  expect(within(usd).getByText("125.00 $")).toHaveAttribute("dir", "ltr");
  expect(screen.getByRole("heading", { name: "Needs you now" })).toBeVisible();
  fireEvent.click(within(lbp).getByRole("button", { name: /Overdue/ }));
  await waitFor(() => expect(calls.at(-1)?.searchParams.get("overdue")).toBe("true"));
  expect(calls.at(-1)?.searchParams.get("currency")).toBe("LBP");
  expect(screen.getByRole("button", { name: "Overdue" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(within(usd).getByRole("button", { name: /Owed to you/ }));
  await waitFor(() => expect(calls.at(-1)?.searchParams.get("paid_state")).toBe("OPEN"));
  expect(calls.at(-1)?.searchParams.get("currency")).toBe("USD");
  const summaries = calls.filter((url) => url.pathname.endsWith("/summary"));
  expect(summaries).toHaveLength(1); // The business-wide summary is independent of list filters.
  for (const url of summaries) expect([...url.searchParams]).toEqual([["tenant_id", "t1"]]);
});

test.each(["en", "ar"])("chips, Filters and Sort share the toolbar above the invoice rows in %s", async (language) => {
  await i18n.changeLanguage(language);
  setup({ waiting: true });
  await screen.findByText("Customer 1");
  const toolbar = document.querySelector(".invoices-front-page > .list-toolbar")!;
  expect(within(toolbar as HTMLElement).getByRole("group", { name: i18n.t("invoicesFrontPage.chips") })).toBeVisible();
  expect(within(toolbar as HTMLElement).getByRole("button", { name: i18n.t("listKit.filters") })).toBeVisible();
  const sort = within(toolbar as HTMLElement).getByRole("button", { name: new RegExp(i18n.t("listKit.sortBy")) });
  fireEvent.click(sort);
  expect(screen.getByRole("menuitemradio", { name: i18n.t("invoicesFrontPage.newest") })).toHaveAttribute("aria-checked", "true");
  fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
  expect(sort).toHaveFocus();
  expect(toolbar.compareDocumentPosition(document.querySelector(".month-group")!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test.each([
  ["Unpaid", "paid_state", "OPEN"], ["Overdue", "overdue", "true"], ["Paid", "paid_state", "PAID"],
  ["Draft", "status", "DRAFT"], ["Cancelled", "status", "CANCELLED"],
])("%s chip sends only its matching API filter and All clears it", async (label, name, value) => {
  const { calls } = setup();
  await screen.findByText("Customer 1");
  const chips = screen.getByRole("group", { name: "Invoice filters" });
  expect(within(chips).getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(within(chips).getByRole("button", { name: label }));
  await waitFor(() => expect(calls.filter((url) => url.pathname.endsWith("/all")).at(-1)?.searchParams.get(name)).toBe(value));
  const query = calls.filter((url) => url.pathname.endsWith("/all")).at(-1)!.searchParams;
  expect([...query.keys()].sort()).toEqual(["tenant_id", "page", "limit", name].sort());
  fireEvent.click(within(chips).getByRole("button", { name: "All" }));
  await waitFor(() => expect(calls.filter((url) => url.pathname.endsWith("/all")).at(-1)?.searchParams.has(name)).toBe(false));
});

test("debounced search passes q, filter sheet applies currency/dates and cancelling drops draft edits", async () => {
  const { calls } = setup();
  await screen.findByText("Customer 1");
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search by invoice number or customer" }), { target: { value: "Corner & Sons" } });
  await waitFor(() => expect(calls.at(-1)?.searchParams.get("q")).toBe("Corner & Sons"));
  fireEvent.click(screen.getByRole("button", { name: "Filters" }));
  fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "LBP" } });
  fireEvent.change(screen.getByLabelText("Date from"), { target: { value: "2026-09-01" } });
  fireEvent.change(screen.getByLabelText("Date to"), { target: { value: "2026-10-31" } });
  fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
  await waitFor(() => expect(calls.at(-1)?.searchParams.get("date_to")).toBe("2026-10-31"));
  expect(calls.at(-1)?.searchParams.get("currency")).toBe("LBP");
  expect(calls.at(-1)?.searchParams.get("date_from")).toBe("2026-09-01");
  expect(calls.at(-1)?.searchParams.get("q")).toBe("Corner & Sons");
  fireEvent.click(screen.getByRole("button", { name: /Filters.*3 active/ }));
  fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USD" } });
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  fireEvent.click(screen.getByRole("button", { name: /Filters.*3 active/ }));
  expect(screen.getByLabelText("Currency")).toHaveValue("LBP");
  fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
  await waitFor(() => expect(calls.at(-1)?.searchParams.has("currency")).toBe(false));
  expect(calls.at(-1)?.searchParams.has("date_from")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  await waitFor(() => expect(calls.at(-1)?.searchParams.has("q")).toBe(false));
  expect(calls.filter((url) => url.pathname.endsWith("/summary"))).toHaveLength(1);
});

test.each([
  ["en", "November 2026", "October 2026", "01/11/2026"],
  ["ar", "تشرين الثاني ٢٠٢٦", "تشرين الأول ٢٠٢٦", "١‏/١١‏/٢٠٢٦"],
])("%s groups and dates confirmed invoices and drafts by the Beirut calendar", async (language, novemberName, octoberName, rowDate) => {
  await i18n.changeLanguage(language);
  setup({ rows: [
    invoice("november", { confirmed_at: "2026-10-31T22:30:00Z" }),
    invoice("draft", { status: "DRAFT", confirmed_at: null, created_at: "2026-11-01T00:30:00+02:00", paid_state: null }),
    invoice("october", { confirmed_at: "2026-10-31T21:30:00Z" }),
  ] });
  const november = await screen.findByRole("region", { name: novemberName });
  expect(within(november).getAllByRole("listitem")).toHaveLength(2);
  for (const name of ["Customer november", "Customer draft"]) {
    const row = within(november).getByRole("link", { name: new RegExp(name) });
    expect(row.querySelector("time")).toHaveTextContent(rowDate);
  }
  const october = screen.getByRole("region", { name: octoberName });
  expect(within(october).getAllByRole("listitem")).toHaveLength(1);
  expect(october).toHaveTextContent("Customer october");
});

test("groups by confirmation date or draft creation month; rows and payment actions use existing addresses", async () => {
  setup({ rows: [
    invoice("1", { is_overdue: true, overdue_age_days: 12 }),
    invoice("2", { paid_state: "PARTLY_PAID", outstanding: "0.0001" }),
    invoice("3", { paid_state: "PAID", outstanding: "0.0000" }),
    invoice("4", { status: "DRAFT", confirmed_at: null, official_invoice_number: null, customer_id: null, customer_name: null, paid_state: null }),
    invoice("5", { status: "CANCELLED", outstanding: "50.0000" }),
  ] });
  const october = await screen.findByRole("region", { name: "October 2026" });
  expect(within(october).getAllByRole("listitem")).toHaveLength(4);
  const september = screen.getByRole("region", { name: "September 2026" });
  expect(september).toHaveTextContent("No customer");
  expect(september).toHaveTextContent("Draft");
  const row = within(october).getByRole("link", { name: /Customer 1/ });
  expect(row).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=1");
  expect(row).toHaveTextContent("Overdue (12 days)");
  expect(row).toHaveTextContent("50.00 $");
  expect(within(row).getByText("2026-1")).toHaveAttribute("dir", "ltr");
  expect(screen.getByText("Partly paid")).toBeVisible();
  expect(screen.getByText("Paid", { selector: ".status-badge" })).toBeVisible();
  for (const [name, id, canPay] of [["Customer 1", "1", true], ["Customer 2", "2", true], ["Customer 3", "3", false], ["No customer", "4", false], ["Customer 5", "5", false]] as const) {
    const trigger = screen.getByRole("button", { name: `More actions for ${name}` });
    fireEvent.click(trigger);
    const menu = screen.getByRole("group", { name: `More actions for ${name}` });
    expect(within(menu).getByRole("link", { name: "Open" })).toHaveAttribute("href", `/workspace?tenant=t1&section=invoices&invoice=${id}`);
    if (canPay) expect(within(menu).getByRole("link", { name: "Record payment" })).toHaveAttribute("href", `/workspace?tenant=t1&section=invoices&invoice=${id}&view=payments`);
    else expect(within(menu).queryByRole("link", { name: "Record payment" })).not.toBeInTheDocument();
    fireEvent.click(trigger);
  }
});

test("Load more appends pages, combines the same month and a filter starts again at page 1", async () => {
  const { calls } = setup({ respond: (url) => url.searchParams.get("paid_state")
    ? page([invoice("paid", { paid_state: "PAID", outstanding: "0" })])
    : url.searchParams.get("page") === "2" ? page([invoice("2")], { page: 2, total: 2, total_pages: 2 }) : page([invoice("1")], { total: 2, total_pages: 2 }) });
  await screen.findByText("Customer 1");
  expect(screen.getByText("1 of 2")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Load more" }));
  await screen.findByText("Customer 2");
  expect(screen.getByText("Customer 1")).toBeVisible();
  expect(screen.getAllByRole("heading", { name: "October 2026" })).toHaveLength(1);
  expect(screen.getByText("2 of 2")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Paid" }));
  await screen.findByText("Customer paid");
  expect(screen.queryByText("Customer 1")).not.toBeInTheDocument();
  expect(calls.at(-1)?.searchParams.get("page")).toBe("1");
});

test.each([0, 1])("New invoice control %s opens a fresh editor address at click time", async (index) => {
  setup();
  await screen.findByText("Customer 1");
  vi.spyOn(Date, "now").mockReturnValue(123456789);
  fireEvent.click(screen.getAllByRole("button", { name: "New invoice" })[index]!);
  expect(screen.getByTestId("address")).toHaveTextContent("/workspace?tenant=t1&section=invoices&fresh=123456789");
});

test.each(["all", "unpaid", "overdue", "paid", "draft", "cancelled"] as const)("empty hint for %s has a working new invoice action", async (chip) => {
  setup({ rows: [] });
  const chips = screen.getByRole("group", { name: "Invoice filters" });
  fireEvent.click(within(chips).getByRole("button", { name: i18n.t(`invoicesFrontPage.${chip}`) }));
  const hint = await screen.findByText(i18n.t(`invoicesFrontPage.empty.${chip}`));
  vi.spyOn(Date, "now").mockReturnValue(456);
  fireEvent.click(within(hint.closest(".empty-hint") as HTMLElement).getByRole("button", { name: "New invoice" }));
  expect(screen.getByTestId("address")).toHaveTextContent("&fresh=456");
});

test.each(["network failure", "browser offline"])("%s shows connection note and keeps creation available", async (kind) => {
  if (kind === "browser offline") vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  setup({ failure: kind === "network failure" ? new TypeError("Failed to fetch") : undefined });
  expect(await screen.findByText("The invoice list needs a connection")).toBeVisible();
  const controls = screen.getAllByRole("button", { name: "New invoice" });
  expect(controls).toHaveLength(2);
  expect(controls.every((control) => !control.hasAttribute("disabled"))).toBe(true);
  fireEvent.click(controls[0]!);
  expect(screen.getByTestId("address").textContent).toMatch(/section=invoices&fresh=\d+$/);
});

test("ordinary API errors show an error with retry instead of an empty result", async () => {
  setup({ failure: new ApiError(503, "UNAVAILABLE", "Temporarily unavailable") });
  expect(await screen.findByText("Temporarily unavailable")).toBeVisible();
  expect(screen.queryByText("No invoices")).not.toBeInTheDocument();
  expect(screen.queryByText("The invoice list needs a connection")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
});

test("Arabic render uses RTL, Arabic month names, translated labels and LTR money", async () => {
  await i18n.changeLanguage("ar");
  setup();
  await screen.findByText("Customer 1");
  expect(screen.getByRole("heading", { name: "الفواتير" }).closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(screen.getByRole("heading", { name: /تشرين الأول/ })).toBeVisible();
  expect(screen.getByText("50.00 $")).toHaveAttribute("dir", "ltr");
  expect(screen.getAllByRole("button", { name: "فاتورة جديدة" })).toHaveLength(2);
});

test("switching business uses distinct summary and list caches without retaining previous rows", async () => {
  const { calls, view, tree } = setup({ respond: (url) => page([invoice(url.searchParams.get("tenant_id")!)]) });
  await screen.findByText("Customer t1");
  view.rerender(tree("t2"));
  await screen.findByText("Customer t2");
  expect(screen.queryByText("Customer t1")).not.toBeInTheDocument();
  expect(calls.filter((url) => url.pathname.startsWith("/api/v1/invoices/") && url.searchParams.get("tenant_id") === "t2")).toHaveLength(2);
});
