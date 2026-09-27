import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { AllCustomers } from "./AllCustomers";
import { moneyMinus, plainAmount } from "./invoiceRevisionLines";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const customer = (index: number) => ({
  id: `c${index}`, tenant_id: "t", name: `Customer ${String(index).padStart(2, "0")}`, phone: `+9617000${String(index).padStart(4, "0")}`,
  address: null, latitude: null, longitude: null, grade: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z",
});

test("all customers page 20 at a time and each expands to its invoices, which open in Invoices (D-101)", async () => {
  await i18n.changeLanguage("en");
  const requested: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = input instanceof Request ? input.url : input.toString();
    requested.push(url);
    const params = new URL(url).searchParams;
    if (url.includes("/api/v1/tenants/t/customers")) {
      const page = Number(params.get("page"));
      const customers = page === 1 ? Array.from({ length: 20 }, (_, index) => customer(index + 1)) : [customer(21)];
      return Promise.resolve(Response.json({ page, limit: 20, total: 21, total_pages: 2, customers }));
    }
    if (url.includes("/api/v1/invoices") && params.get("customer_id") === "c1") {
      return Promise.resolve(Response.json({ page: 1, limit: 20, total: 2, total_pages: 1, invoices: [
        { id: "inv-2", status: "CONFIRMED", official_invoice_number: "2026-000002", confirmed_at: "2026-09-20T10:00:00Z", created_at: "2026-09-19T10:00:00Z", currency: "USD", net_sales: "25.0000", total_due: "25.0000", server_revision_number: 1 },
        { id: "inv-1", status: "DRAFT", official_invoice_number: null, confirmed_at: null, created_at: "2026-09-18T10:00:00Z", currency: "LBP", net_sales: "900000.0000", total_due: "900000.0000", server_revision_number: 3 },
      ] }));
    }
    if (url.includes("/api/v1/invoices")) return Promise.resolve(Response.json({ page: 1, limit: 20, total: 0, total_pages: 0, invoices: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));
  const { container } = render(<MemoryRouter><AllCustomers tenantId="t" /></MemoryRouter>);
  // Nothing is fetched until the section is opened.
  expect(requested).toHaveLength(0);
  const details = container.querySelector("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  const list = await screen.findByRole("list", { name: "All customers" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(20);
  expect(requested[0]).toContain("page=1&limit=20");
  expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();

  // Expanding a customer lists every invoice with status, number and total; each opens in Invoices.
  fireEvent.click(within(list).getAllByRole("button", { name: /Invoices/ })[0]!);
  const invoices = await screen.findByRole("list", { name: "Invoices of Customer 01" });
  expect(within(invoices).getByRole("link", { name: "2026-000002" })).toHaveAttribute("href", "/workspace?tenant=t&section=invoices&invoice=inv-2");
  expect(within(invoices).getByRole("link", { name: "R3" })).toHaveAttribute("href", "/workspace?tenant=t&section=invoices&invoice=inv-1");
  expect(within(invoices).getByText("Confirmed")).toBeInTheDocument();
  expect(within(invoices).getByText("Draft")).toBeInTheDocument();
  expect(within(invoices).getByText("900000.0000 LBP")).toBeInTheDocument();
  expect(requested.some((url) => url.includes("customer_id=c1") && url.includes("limit=20"))).toBe(true);
  expect(within(list).getAllByRole("link", { name: "Open record" })[0]).toHaveAttribute("href", "/workspace?tenant=t&section=customers&customer=c1");

  // A customer with none says so.
  fireEvent.click(within(list).getAllByRole("button", { name: /Invoices/ })[1]!);
  expect(await screen.findByText("No invoices for this customer yet.")).toBeInTheDocument();

  // Next page.
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() => expect(within(screen.getByRole("list", { name: "All customers" })).getAllByRole("listitem")).toHaveLength(1));
  expect(screen.getByText("Customer 21")).toBeInTheDocument();
});

test("invoice-level discount and markup are what remains after the line amounts, exactly", () => {
  expect(moneyMinus("1.5000", ["0.5000", "0.0000"])).toBe("1");
  expect(moneyMinus("0.2500", ["0.2500"])).toBe("0");
  expect(moneyMinus("10.0001", ["0.0001", "3.3333"])).toBe("6.6667");
  expect(moneyMinus("0", ["1.25"])).toBe("-1.25");
  expect(plainAmount("2.0000")).toBe("2");
  expect(plainAmount("0.1200")).toBe("0.12");
});
