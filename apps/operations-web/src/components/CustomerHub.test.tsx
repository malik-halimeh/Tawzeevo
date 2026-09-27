import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import i18n from "../i18n";
import { InvoiceEditor } from "./InvoiceEditor";
import { TenantWorkspace } from "./TenantWorkspace";

const tenantId = "44444444-4444-4444-4444-444444444444";
const owner = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenantId, tenant_name: "North Route", tenant_status: "ACTIVE", role: "owner" } as const;
const maya = { id: "66666666-6666-6666-6666-666666666666", tenant_id: tenantId, name: "Maya Market", phone: "+96170123456", address: "Hamra", latitude: null, longitude: null, grade: "A", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
const urlOf = (input: RequestInfo | URL) => (typeof input === "string" ? input : input instanceof URL ? input.href : input.url);

let obligationUrls: string[] = [];
beforeEach(async () => {
  await i18n.changeLanguage("en");
  obligationUrls = [];
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = urlOf(input);
    if (url.includes("/customers/search")) return Promise.resolve(json({ customers: [] }));
    if (url.includes(`/tenants/${tenantId}/customers/${maya.id}`)) return Promise.resolve(json(maya));
    if (url.includes("/customer-ledger/settings")) return Promise.resolve(json({ tenant_id: tenantId, customer_overdue_threshold_days: null }));
    if (url.includes("/customer-ledger/debts")) return Promise.resolve(json({ debts: [{ customer_id: maya.id, customer_name: maya.name, customer_phone: maya.phone, currency: "LBP", balance: "900000.0000", oldest_unpaid_at: null, overdue_age_days: null, overdue_threshold_days: null, is_overdue: false }] }));
    if (url.includes("/balances")) return Promise.resolve(json({ customer_id: maya.id, customer_name: maya.name, balances: [] }));
    if (url.includes("/obligations")) { obligationUrls.push(url); return Promise.resolve(json({ customer_id: maya.id, currency: "USD", obligations: [] })); }
    if (url.includes("/api/v1/suppliers?")) return Promise.resolve(json({ suppliers: [] }));
    if (url.includes("/categories?")) return Promise.resolve(json({ categories: [] }));
    return Promise.resolve(json({ detail: { code: "NOT_FOUND", message: url } }, 404));
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const withProviders = (ui: React.ReactNode, path = "/") => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
  </QueryClientProvider>
);

test("a search that finds nobody offers to add a customer with that phone, already filled in", async () => {
  render(withProviders(<TenantWorkspace contexts={[owner]} />, "/workspace?section=customers"));
  fireEvent.change(await screen.findByLabelText("Phone"), { target: { value: "+96171999888" } });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add customer with +96171999888" }));
  const form = await screen.findByRole("heading", { name: "Add customer" });
  expect(form).toBeInTheDocument();
  expect(screen.getAllByLabelText("Phone").find((input) => input.closest("form")?.classList.contains("form-grid"))).toHaveValue("+96171999888");
});

test("opened for a customer, the invoice editor has them chosen and can open straight on payments in their currency", async () => {
  render(withProviders(<InvoiceEditor customerId={maya.id} initialCurrency="LBP" initialView="payments" membershipId="m1" tenantId={tenantId} />));
  const context = await screen.findByRole("region", { name: "Customer and currency" });
  expect(await within(context).findByText("Maya Market")).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Payments" })).toHaveAttribute("aria-pressed", "true");
  await waitFor(() => expect(obligationUrls.some((url) => url.includes("currency=LBP"))).toBe(true));
});

test("a debt row records a payment for that customer in that currency when no invoice is in progress", async () => {
  render(withProviders(<InvoiceEditor membershipId="m1" tenantId={tenantId} />));
  fireEvent.click(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Balances" }));
  const register = (await screen.findByText("Maya Market")).closest("div.debt-row") as HTMLElement;
  fireEvent.click(within(register).getByRole("button", { name: "Record payment" }));
  await waitFor(() => expect(within(screen.getByRole("group", { name: "Invoice views" })).getByRole("button", { name: "Payments" })).toHaveAttribute("aria-pressed", "true"));
  expect(within(screen.getByRole("region", { name: "Customer and currency" })).getByRole("textbox")).toHaveValue("LBP");
  await waitFor(() => expect(obligationUrls.some((url) => url.includes("currency=LBP"))).toBe(true));
});
