import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { Customer } from "../../api/types";
import i18n from "../../i18n";
import { createCustomerOffline, updateCustomerOffline } from "../../offline/outbox";
import { TenantWorkspace } from "../TenantWorkspace";
import { SEARCH_DELAY_MS } from "../listKit/ListHeader";
import { CustomersList } from "./CustomersList";

vi.mock("../../offline/outbox", async (original) => ({
  ...await original<typeof import("../../offline/outbox")>(),
  createCustomerOffline: vi.fn(), updateCustomerOffline: vi.fn(),
}));

const owner = { membership_id: "m1", tenant_id: "t1", tenant_name: "Cedar Route", tenant_status: "ACTIVE", role: "owner" } as const;
const customer: Customer = {
  id: "c1", tenant_id: "t1", name: "Maya Market", phone: "+96170123456",
  address: "Hamra", latitude: "33.89", longitude: "35.50", grade: "A",
  created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
};
const withBalances = { ...customer, balances: [{ currency: "USD", balance: "42.5000" }, { currency: "LBP", balance: "900000.0000" }] };
const other = { ...customer, id: "c2", name: "Cedar Corner", address: null, latitude: null, longitude: null, grade: null, balances: [] };
const page = (customers = [withBalances], overrides = {}) => ({ page: 1, limit: 20, total: customers.length, total_pages: 1, customers, ...overrides });

function Address() {
  const location = useLocation();
  return <output data-testid="address">{location.pathname}{location.search}</output>;
}

function setup({ listOnly = false, respond, phoneMatches = [customer], failure, record = customer }: {
  listOnly?: boolean;
  respond?: (url: URL) => ReturnType<typeof page> | Promise<ReturnType<typeof page>>;
  phoneMatches?: Customer[];
  failure?: "validation" | "offline";
  record?: Customer;
} = {}) {
  const calls: { url: URL; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    const method = init?.method ?? "GET";
    const body: unknown = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ url, method, body });
    if (url.pathname === "/api/v1/tenants/t1/customers") {
      if (method === "GET") return Response.json(respond ? await respond(url) : page());
      if (failure === "offline") throw new TypeError("Failed to fetch");
      if (failure === "validation") return Response.json({ detail: { code: "VALIDATION_ERROR", message: "Location is not valid" } }, { status: 422 });
      return Response.json({ ...record, ...(body as object), id: "created" });
    }
    if (url.pathname.endsWith("/customers/search")) return Response.json({ customers: phoneMatches });
    if (url.pathname.endsWith(`/customers/${record.id}`)) {
      if (method === "PUT" && failure === "offline") throw new TypeError("Failed to fetch");
      return Response.json({ ...record, ...(body as object) });
    }
    if (url.pathname.endsWith("/categories")) return Response.json({ categories: [] });
    if (url.pathname.endsWith("/balances")) return Response.json({ balances: withBalances.balances });
    if (url.pathname.endsWith("/priorities") || url.pathname.endsWith("/inactivity")) return Response.json({ groups: [] });
    if (url.pathname.endsWith("/access-link")) return Response.json({ active: null, effective_policy: "LINK", policy_override: null, tenant_policy: "LINK", available_policies: ["LINK"], verified_sessions: 0 });
    if (url.pathname === "/api/v1/invoices") return Response.json({ page: 1, total_pages: 1, invoices: [
      { id: "inv-1", status: "DRAFT", official_invoice_number: null, confirmed_at: null, created_at: "2026-09-01T00:00:00Z", currency: "USD", net_sales: "12.0000", total_due: "12.0000", server_revision_number: 3 },
    ] });
    throw new Error(`Unexpected request: ${method} ${url}`);
  }));
  const tree = <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/workspace?tenant=t1&section=customers"]}>
      {listOnly ? <CustomersList onEdit={vi.fn()} onInvoices={vi.fn()} onShopLink={vi.fn()} refreshKey={0} tenantId="t1" /> : <TenantWorkspace contexts={[owner]} />}
      <Address />
    </MemoryRouter>
  </QueryClientProvider>;
  const view = render(tree);
  return { calls, view };
}

const listCalls = (calls: ReturnType<typeof setup>["calls"]) => calls.filter((call) => call.url.pathname === "/api/v1/tenants/t1/customers" && call.method === "GET");
const actionMenu = () => screen.getByRole("group", { name: "More actions for Maya Market" });
async function openMenu() { fireEvent.click(await screen.findByRole("button", { name: "More actions for Maya Market" })); return actionMenu(); }

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test("the server list shows the count and balances separately, and rows open the customer address and record", async () => {
  setup({ respond: () => page([withBalances, other]) });
  const list = await screen.findByRole("list", { name: "All customers" });
  const row = within(list).getByRole("link", { name: /Maya Market/ });
  expect(row).toHaveAttribute("href", "/workspace?tenant=t1&section=customers&customer=c1");
  expect(within(row).getByText("42.5000 USD")).toHaveAttribute("dir", "ltr");
  expect(within(row).getByText("900000.0000 LBP")).toHaveAttribute("dir", "ltr");
  expect(within(row).getByText(customer.phone)).toHaveAttribute("dir", "ltr");
  expect(row).not.toHaveTextContent("900042");
  expect(within(list).getByRole("link", { name: /Cedar Corner/ }).querySelector(".list-row-amount")).toBeNull();
  expect(screen.getByRole("button", { name: "Sort by Name" })).toBeInTheDocument();
  fireEvent.click(row);
  const record = await screen.findByRole("article", { name: "Maya Market" });
  await waitFor(() => expect(within(record).getByRole("heading", { level: 2 })).toHaveFocus());
  expect(screen.getByTestId("address")).toHaveTextContent("customer=c1");
  expect(screen.getByRole("region", { name: "Customers" })).toHaveClass("show-detail");
  fireEvent.click(within(record).getByRole("button", { name: "All customers" }));
  await waitFor(() => expect(row).toHaveFocus());
  expect(screen.getByTestId("address")).not.toHaveTextContent("customer=");
});

test("search waits for two characters and the list-kit debounce, sends literal Arabic to the server and clears on close", async () => {
  const { calls } = setup({ listOnly: true });
  await screen.findByRole("list", { name: "All customers" });
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  const search = screen.getByRole("searchbox", { name: "Search by name or phone" });
  fireEvent.change(search, { target: { value: "م" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS); });
  expect(listCalls(calls)).toHaveLength(1);
  fireEvent.change(search, { target: { value: "مَـايَا" } });
  await act(async () => { await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS - 1); });
  expect(listCalls(calls)).toHaveLength(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(listCalls(calls).at(-1)?.url.searchParams.get("q")).toBe("مَـايَا");
  expect(search).toHaveFocus();
  await act(async () => { fireEvent.keyDown(search, { key: "Escape" }); await Promise.resolve(); });
  expect(listCalls(calls).at(-1)?.url.searchParams.has("q")).toBe(false);
});

test.each(["en", "ar"])("%s customer requests omit short searches, trim valid searches and cap pasted text", async (language) => {
  await i18n.changeLanguage(language);
  const { calls } = setup({ listOnly: true });
  await screen.findByRole("list", { name: i18n.t("allCustomers.title") });
  expect(listCalls(calls)).toHaveLength(1);
  expect(listCalls(calls).at(0)?.url.searchParams.has("q")).toBe(false);

  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("button", { name: i18n.t("common.search") }));
  const search = screen.getByRole("searchbox", { name: i18n.t("customersPage.search") });
  const letter = language === "ar" ? "م" : "M";
  const type = async (value: string) => {
    fireEvent.change(search, { target: { value } });
    await act(async () => { await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS); });
  };
  const latestParams = () => listCalls(calls).at(-1)!.url.searchParams;

  await type(letter);
  expect(listCalls(calls)).toHaveLength(1);
  expect(latestParams().has("q")).toBe(false);

  await type(`  ${letter.repeat(2)}  `);
  expect(listCalls(calls)).toHaveLength(2);
  expect(latestParams().get("q")).toBe(letter.repeat(2));

  await type(letter.repeat(70));
  expect(listCalls(calls)).toHaveLength(3);
  expect(latestParams().get("q")).toBe(letter.repeat(64));

  await type(`  ${letter}  `);
  expect(listCalls(calls)).toHaveLength(4);
  expect(latestParams().has("q")).toBe(false);

  await type("   ");
  expect(latestParams().has("q")).toBe(false);
});

test("Load more appends, each sort resets to page one and a late prior page cannot replace the new sort", async () => {
  let finishOldPage: ((value: ReturnType<typeof page>) => void) | undefined;
  const { calls } = setup({ listOnly: true, respond: (url) => {
    if (url.searchParams.get("page") === "2") return new Promise((resolve) => { finishOldPage = resolve; });
    return page(url.searchParams.get("sort") === "name" ? [withBalances] : [other], { total: 2, total_pages: 2 });
  } });
  await screen.findByRole("list", { name: "All customers" });
  fireEvent.click(screen.getByRole("button", { name: "Load more" }));
  await waitFor(() => expect(finishOldPage).toBeDefined());
  await act(async () => { finishOldPage?.(page([other], { page: 2, total: 2, total_pages: 2 })); await Promise.resolve(); });
  expect(within(screen.getByRole("list", { name: "All customers" })).getAllByRole("link")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Sort by Name" }));
  fireEvent.click(screen.getByRole("menuitemradio", { name: "Newest" }));
  await waitFor(() => expect(listCalls(calls).at(-1)?.url.searchParams.get("sort")).toBe("newest"));
  await screen.findByRole("link", { name: /Cedar Corner/ });
  expect(listCalls(calls).at(-1)?.url.searchParams.get("page")).toBe("1");
  expect(screen.queryByRole("link", { name: /Maya Market/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Load more" }));
  fireEvent.click(screen.getByRole("button", { name: "Sort by Newest" }));
  fireEvent.click(screen.getByRole("menuitemradio", { name: "Who owes most" }));
  await screen.findByRole("link", { name: /Cedar Corner/ });
  await act(async () => { finishOldPage?.(page([withBalances], { page: 2, total: 2, total_pages: 2 })); await Promise.resolve(); });
  expect(screen.queryByRole("link", { name: /Maya Market/ })).not.toBeInTheDocument();
  expect(listCalls(calls).at(-1)?.url.searchParams.get("sort")).toBe("owes_most");
});

test("row actions retain invoice/payment destinations, edit, the existing shop controls and every invoice", async () => {
  const { calls } = setup();
  let menu = await openMenu();
  expect(within(menu).getByRole("link", { name: "New invoice" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&customer=c1");
  expect(within(menu).getByRole("link", { name: "Record payment" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&view=payments&customer=c1");
  fireEvent.click(within(menu).getByRole("button", { name: "Shop link" }));
  const record = screen.getByRole("article", { name: "Maya Market" });
  expect(await within(record).findByRole("button", { name: "Create personalized link" })).toBeInTheDocument();
  expect(calls.some((call) => call.url.pathname.endsWith("/customers/c1/access-link"))).toBe(true);
  fireEvent.click(within(record).getByRole("button", { name: "All customers" }));
  menu = await openMenu();
  fireEvent.click(within(menu).getByRole("button", { name: "Invoices" }));
  const invoices = await screen.findByRole("list", { name: "Invoices of Maya Market" });
  expect(within(invoices).getByRole("link", { name: "R3" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=inv-1");
  expect(calls.some((call) => call.url.pathname === "/api/v1/invoices" && call.url.searchParams.get("customer_id") === "c1")).toBe(true);
  fireEvent.click(within(record).getByRole("button", { name: "All customers" }));
  menu = await openMenu();
  fireEvent.click(within(menu).getByRole("button", { name: "Edit" }));
  const form = screen.getByRole("heading", { name: "Edit customer" }).closest("article")!;
  expect(within(form).getByLabelText("Customer name")).toHaveValue(customer.name);
  expect(form.querySelector("details")).toHaveAttribute("open");
  expect(within(form).getByLabelText("Address")).toHaveValue("Hamra");
});

test("a failed next page keeps the loaded rows and retries that page before Load more can advance", async () => {
  let recovered = false;
  const { calls } = setup({ listOnly: true, respond: (url) => {
    const next = Number(url.searchParams.get("page"));
    if (next === 2 && !recovered) throw new Error("Page unavailable");
    return page(next === 1 ? [withBalances] : [other], { page: next, total: 3, total_pages: 3 });
  } });
  await screen.findByRole("list", { name: "All customers" });
  fireEvent.click(screen.getByRole("button", { name: "Load more" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Page unavailable");
  expect(screen.getByRole("link", { name: /Maya Market/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Load more" })).toBeDisabled();
  recovered = true;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByRole("link", { name: /Cedar Corner/ });
  expect(listCalls(calls).map((call) => call.url.searchParams.get("page"))).toEqual(["1", "2", "2"]);
  expect(screen.getByRole("button", { name: "Load more" })).toBeEnabled();
});

test.each([
  { address: "Hamra", grade: null, latitude: null, longitude: null },
  { address: null, grade: "B" as const, latitude: null, longitude: null },
  { address: null, grade: null, latitude: "0", longitude: "0" },
])("optional fields open when editing a record with saved address, grade or location: %o", async (optional) => {
  const saved = { ...customer, ...optional };
  setup({ record: saved, respond: () => page([{ ...saved, balances: [] }]) });
  fireEvent.click(within(await openMenu()).getByRole("button", { name: "Edit" }));
  expect(screen.getByText("Show more fields").closest("details")).toHaveAttribute("open");
});

test("Fab opens required fields first; optional server validation reveals the disclosure without clearing values", async () => {
  setup({ failure: "validation" });
  await screen.findByRole("list", { name: "All customers" });
  fireEvent.click(screen.getByRole("button", { name: "New customer" }));
  const form = screen.getByRole("heading", { name: "Add customer" }).closest("article")!;
  expect(form.querySelector("details")).not.toHaveAttribute("open");
  const inputs = form.querySelectorAll("input");
  expect(inputs[0]).toHaveAttribute("required");
  expect(inputs[1]).toHaveAttribute("required");
  fireEvent.change(within(form).getByLabelText("Customer name"), { target: { value: "New shop" } });
  fireEvent.change(within(form).getByLabelText("Phone"), { target: { value: "+96171999888" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Location is not valid");
  await waitFor(() => expect(form.querySelector("details")).toHaveAttribute("open"));
  expect(within(form).getByLabelText("Customer name")).toHaveValue("New shop");
});

test("the separate exact-phone lookup keeps duplicate records and its address unchanged", async () => {
  const { calls } = setup({ phoneMatches: [customer, { ...other, phone: customer.phone }] });
  const lookup = screen.getByRole("heading", { name: "Find every matching customer" }).closest("article")!;
  fireEvent.change(within(lookup).getByLabelText("Phone"), { target: { value: "70 123 456" } });
  fireEvent.click(within(lookup).getByRole("button", { name: "Search" }));
  const results = await screen.findByRole("list", { name: "Matching customers" });
  expect(within(results).getAllByRole("button")).toHaveLength(2);
  expect(calls.find((call) => call.url.pathname.endsWith("/customers/search"))?.url.searchParams.get("phone")).toBe("70 123 456");
});

test.each(["create", "edit"] as const)("%s still uses the workspace's offline queue handler", async (mode) => {
  vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(false);
  vi.mocked(createCustomerOffline).mockResolvedValue({ ...other, id: "local-customer" } as never);
  vi.mocked(updateCustomerOffline).mockResolvedValue({ ...customer, name: "Queued shop" } as never);
  setup({ failure: "offline" });
  await screen.findByRole("list", { name: "All customers" });
  if (mode === "create") fireEvent.click(screen.getByRole("button", { name: "New customer" }));
  else fireEvent.click(within(await openMenu()).getByRole("button", { name: "Edit" }));
  const form = screen.getByRole("heading", { name: mode === "create" ? "Add customer" : "Edit customer" }).closest("article")!;
  fireEvent.change(within(form).getByLabelText("Customer name"), { target: { value: "Queued shop" } });
  fireEvent.change(within(form).getByLabelText("Phone"), { target: { value: customer.phone } });
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(mode === "create" ? createCustomerOffline : updateCustomerOffline).toHaveBeenCalledOnce());
  await waitFor(() => expect(screen.queryByRole("heading", { name: mode === "create" ? "Add customer" : "Edit customer" })).not.toBeInTheDocument());
});

test("Arabic renders translated list controls and isolated LTR phones and amounts", async () => {
  await i18n.changeLanguage("ar");
  const { view } = setup();
  view.container.dir = "rtl";
  expect(await screen.findByRole("heading", { name: "العملاء", level: 1 })).toBeInTheDocument();
  const list = await screen.findByRole("list", { name: i18n.t("allCustomers.title") });
  expect(list.closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(within(list).getByText("42.5000 USD")).toHaveAttribute("dir", "ltr");
  expect(within(list).getByText(customer.phone)).toHaveAttribute("dir", "ltr");
  fireEvent.click(screen.getByRole("button", { name: "الترتيب حسب الاسم" }));
  expect(screen.getByRole("menuitemradio", { name: "الأكثر مديونية" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "عميل جديد" }));
  expect(screen.getByText("إظهار المزيد من الحقول")).toBeInTheDocument();
});
