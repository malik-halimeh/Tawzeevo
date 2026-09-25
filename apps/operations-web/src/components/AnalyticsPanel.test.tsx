import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { AnalyticsPanel } from "./AnalyticsPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

// The panel also hosts the cash position and unusual changes (D-089), which read through React Query.
const renderPanel = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AnalyticsPanel tenantId="t1" /></QueryClientProvider>);

test("owner sees per-currency figures, profit with coverage and the event flow, and can change the period", async () => {
  await i18n.changeLanguage("en");
  const periods: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = input instanceof Request ? input.url : input.toString();
    const period = new URL(url, "http://x").searchParams.get("period") ?? "";
    if (url.includes("/analytics/overview")) { periods.push(period); return Promise.resolve(Response.json({ period: { key: period, start: null, end: "2026-09-19T00:00:00Z", timezone: "Asia/Beirut" }, confirmed_invoices: 2, invoiced_sales: [{ currency: "LBP", amount: "90000.0000" }, { currency: "USD", amount: "24.2500" }], customer_receipts: [{ currency: "USD", amount: "10.0000" }], customer_refunds: [], customer_outstanding: [{ currency: "USD", amount: "114.2500" }], customer_credit: [], supplier_payable: [], supplier_credit: [], gross_profit: [{ currency: "USD", gross_profit: "8.2500", covered_lines: 1, total_lines: 2, uncovered_lines: 1, coverage_percent: "50.0000" }] })); }
    if (url.includes("/tenants/t1/customers")) return Promise.resolve(Response.json({ customers: [] }));
    if (url.includes("/analytics/events")) return Promise.resolve(Response.json({ totals: [{ currency: "USD", confirmations: "50.0000", edit_deltas: "-12.0000", cancellations: "-13.7500", net_effect: "24.2500" }], monthly: [{ currency: "USD", month: "2026-09", net_effect: "24.2500" }] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));

  renderPanel();
  expect(await screen.findByText("90000.0000 LBP · 24.2500 USD")).toBeInTheDocument(); // separate, never summed
  expect(screen.getByText("50.0000% (1/2)")).toBeInTheDocument(); // profit never without coverage
  expect(screen.getByText("1 line without a cost")).toBeInTheDocument();
  expect(screen.getByText(/2 confirmed invoices in the period/)).toBeInTheDocument();
  expect(screen.getByText(/Currencies are listed separately on purpose/)).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Event flow" })).toHaveTextContent("-13.7500");
  fireEvent.change(screen.getByLabelText("Period"), { target: { value: "1y" } });
  expect(await screen.findByText(/Last year/)).toBeInTheDocument();
  expect(periods).toEqual(["30d", "1y"]);
});

test("wide tables scroll inside labelled regions a keyboard can reach", async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = input instanceof Request ? input.url : input.toString();
    if (url.includes("/analytics/overview")) return Promise.resolve(Response.json({ period: { key: "30d", start: null, end: "2026-09-19T00:00:00Z", timezone: "Asia/Beirut" }, confirmed_invoices: 1, invoiced_sales: [{ currency: "USD", amount: "24.2500" }], customer_receipts: [], customer_refunds: [], customer_outstanding: [], customer_credit: [], supplier_payable: [], supplier_credit: [], gross_profit: [{ currency: "USD", gross_profit: "8.2500", covered_lines: 1, total_lines: 1, uncovered_lines: 0, coverage_percent: "100.0000" }] }));
    if (url.includes("/analytics/events")) return Promise.resolve(Response.json({ totals: [{ currency: "USD", confirmations: "24.2500", edit_deltas: "0.0000", cancellations: "0.0000", net_effect: "24.2500" }], monthly: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));

  renderPanel();
  for (const name of ["Historical gross profit", "Event flow"]) {
    const region = await screen.findByRole("region", { name });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(region).toContainElement(screen.getByRole("table", { name }));
  }
});
