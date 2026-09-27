import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OwnerTodayStrip } from "./OwnerTodayStrip";
import { PENDING_ORDERS_KEY } from "./pendingOrders";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const delivered = (id: string, invoice: string, customer: string, name: string, number: string, completed: string) => ({ id, invoice_id: invoice, official_invoice_number: number, customer_id: customer, customer_name: name, currency: "USD", completed_at: completed });

function renderStrip(tasks: unknown[], obligations: Record<string, unknown[]>, waiting = 0) {
  const obligationCalls: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost");
    if (url.pathname === "/api/v1/delivery-tasks") {
      expect(url.searchParams.get("status")).toBe("COMPLETED");
      return Promise.resolve(Response.json({ tasks, eligible_members: [], sole_operator: true }));
    }
    const customer = /\/payments\/customers\/([^/]+)\/obligations/.exec(url.pathname)?.[1];
    if (customer) { obligationCalls.push(`${customer}:${url.searchParams.get("currency")}`); return Promise.resolve(Response.json({ customer_id: customer, currency: "USD", obligations: obligations[customer] ?? [] })); }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (waiting) client.setQueryData([PENDING_ORDERS_KEY, "t1"], Array.from({ length: waiting }, (_, index) => ({ id: `o${index}`, contact_name: "Rami", created_at: "2026-09-27T08:00:00Z" })));
  const view = render(<QueryClientProvider client={client}><MemoryRouter><OwnerTodayStrip tenantId="t1" /></MemoryRouter></QueryClientProvider>);
  return { view, obligationCalls };
}

test("lists delivered invoices whose amount is still open, and links each to its payment", async () => {
  const { obligationCalls } = renderStrip(
    [delivered("t1", "inv1", "c1", "Corner Shop", "2026-000001", "2026-09-27T09:00:00Z"), delivered("t2", "inv2", "c1", "Corner Shop", "2026-000002", "2026-09-27T08:00:00Z"), delivered("t3", "inv3", "c2", "Hill Market", "2026-000003", "2026-09-26T08:00:00Z")],
    {
      c1: [{ source_type: "INVOICE", source_id: "inv1", outstanding_amount: "30.0000" }, { source_type: "OPENING_BALANCE", source_id: null, outstanding_amount: "5.0000" }],
      c2: [],
    },
  );
  const list = await screen.findByRole("list", { name: "Delivered, payment not recorded yet" });
  const rows = within(list).getAllByRole("listitem");
  expect(rows).toHaveLength(1); // inv2 is paid (no open obligation) and inv3's customer owes nothing
  expect(rows[0]).toHaveTextContent("Corner Shop · 2026-000001");
  expect(rows[0]).toHaveTextContent("30.0000 USD");
  expect(within(rows[0]!).getByRole("link", { name: "Record payment" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=inv1&view=payments");
  expect(obligationCalls.sort()).toEqual(["c1:USD", "c2:USD"]); // one request per customer and currency
  expect(document.body.textContent).not.toMatch(/\bpaid\b/i);
});

test("shows the orders waiting for review from the shell's cached count, and nothing when there is nothing to do", async () => {
  renderStrip([], {}, 2);
  expect(await screen.findByText("2 awaiting review")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Review" })).toHaveAttribute("href", "/workspace?tenant=t1&section=orders");
  cleanup();

  const { view } = renderStrip([], {});
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(view.container).toBeEmptyDOMElement();
});
