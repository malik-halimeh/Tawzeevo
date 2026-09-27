import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { CollectionInbox } from "./CollectionInbox";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const report = { id: "c1", status: "PENDING", kind: "PARTIAL", amount: "12.5000", currency: "USD", task_id: "t1", invoice_id: "inv1", official_invoice_number: "2026-000007", customer_id: "cu1", customer_name: "Corner Shop", reporter_name: "Karim", created_at: "2026-09-27T09:00:00Z" };

function stub(rows: unknown[]) {
  const writes: Array<{ path: string; body: unknown }> = [];
  let pending = rows;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost");
    if ((init?.method ?? "GET") !== "GET") {
      writes.push({ path: url.pathname, body: typeof init?.body === "string" ? JSON.parse(init.body) : null });
      pending = [];
      return Promise.resolve(Response.json({ ...report, status: "CONFIRMED" }));
    }
    return Promise.resolve(Response.json({ reports: pending }));
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><CollectionInbox tenantId="tn" /></MemoryRouter></QueryClientProvider>);
  return writes;
}

test("the owner confirms a reported payment, which records the receipt (D-114)", async () => {
  const writes = stub([report]);
  expect(await screen.findByText("Corner Shop")).toBeInTheDocument();
  expect(screen.getByText("12.5000 USD")).toBeInTheDocument();
  expect(screen.getByText(/Paid partly · Karim/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm payment" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, record the payment" }));
  expect(await screen.findByText("Payment recorded for the invoice.")).toBeInTheDocument();
  expect(writes).toEqual([{ path: "/api/v1/collection-reports/c1/confirm", body: null }]);
});

test("'Not paid' is acknowledged and a report can be rejected with a reason", async () => {
  let writes = stub([{ ...report, kind: "NONE", amount: null }]);
  fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, acknowledge" }));
  expect(await screen.findByText("Noted: not paid.")).toBeInTheDocument();
  expect(writes[0]!.path).toBe("/api/v1/collection-reports/c1/confirm");
  cleanup();

  writes = stub([report]);
  fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
  fireEvent.change(screen.getByLabelText("Reason (required)"), { target: { value: "No money handed over" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Reject" }).find((button) => button.className.includes("button-danger"))!);
  await waitFor(() => expect(writes).toEqual([{ path: "/api/v1/collection-reports/c1/reject", body: { reason: "No money handed over" } }]));
});
