import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OwnerTodayStrip } from "./OwnerTodayStrip";
import { PickupInbox, ReportPickupForm } from "./PickupReports";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const report = {
  id: "r1", status: "PENDING", list_id: "l1", list_title: "Monday list", supplier_id: "s1", supplier_name: "Bekaa Wholesale", reporter_name: "Karim",
  currency: "USD", total: "30.0000", notes: null, reason: null, created_at: "2026-09-27T08:00:00Z",
  lines: [{ procurement_item_id: "i1", product_id: "p1", product_name: "Cedar Water", quantity: "4.0000", unit_cost: "7.5000" }],
};

function stub() {
  const writes: Array<{ path: string; body: unknown }> = [];
  let pending = [report];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost");
    if ((init?.method ?? "GET") !== "GET") {
      writes.push({ path: url.pathname, body: typeof init?.body === "string" ? JSON.parse(init.body) : null });
      if (url.pathname.endsWith("/confirm") || url.pathname.endsWith("/reject")) pending = [];
      return Promise.resolve(Response.json({ ...report, status: "CONFIRMED" }, { status: 201 }));
    }
    if (url.pathname === "/api/v1/procurement/pickup-reports") return Promise.resolve(Response.json({ reports: pending }));
    if (url.pathname === "/api/v1/delivery-tasks") return Promise.resolve(Response.json({ tasks: [] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
  return writes;
}
const wrap = (ui: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);

test("the runner reports quantities and prices paid, once per attempt, and nothing else happens (D-106)", async () => {
  const writes = stub();
  wrap(<ReportPickupForm items={[{ item_id: "i1", product_name: "Cedar Water", remaining_quantity: "6.0000" }, { item_id: "i2", product_name: "Rice", remaining_quantity: "2.0000" }]} listId="l1" supplierId="s1" tenantId="t1" />);
  fireEvent.click(screen.getByRole("button", { name: "Report this pickup" }));
  const quantities = screen.getAllByLabelText("Quantity picked up");
  expect(quantities[0]).toHaveValue(6);
  fireEvent.change(quantities[0]!, { target: { value: "4" } });
  fireEvent.change(quantities[1]!, { target: { value: "0" } }); // not picked up: left out
  fireEvent.change(screen.getAllByLabelText("Unit price paid (USD)")[0]!, { target: { value: "7.5" } });
  fireEvent.click(screen.getByRole("button", { name: "Send to the owner" }));
  expect(await screen.findByText("Sent. The owner will confirm it.")).toBeInTheDocument();
  expect(writes).toHaveLength(1);
  expect(writes[0]!.path).toBe("/api/v1/procurement/pickup-reports");
  expect(writes[0]!.body).toMatchObject({ list_id: "l1", supplier_id: "s1", currency: "USD", lines: [{ procurement_item_id: "i1", quantity: "4", unit_cost: "7.5" }] });
  expect(typeof (writes[0]!.body as { idempotency_key: string }).idempotency_key).toBe("string");
});

test("the owner sees pickups to confirm on Today and confirms or rejects with a reason", async () => {
  let writes = stub();
  wrap(<OwnerTodayStrip tenantId="t1" />);
  expect(await screen.findByText("1 pickup to confirm")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Review/ })).toHaveAttribute("href", "/workspace?tenant=t1&section=procurement");
  cleanup();

  writes = stub();
  wrap(<PickupInbox tenantId="t1" />);
  expect(await screen.findByText(/Bekaa Wholesale/)).toBeInTheDocument();
  expect(screen.getByText("30.0000 USD")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm purchase" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, record the purchase" }));
  expect(await screen.findByText("Purchase recorded from the pickup.")).toBeInTheDocument();
  expect(writes.map((write) => write.path)).toEqual(["/api/v1/procurement/pickup-reports/r1/confirm"]);
  cleanup();

  writes = stub();
  wrap(<PickupInbox tenantId="t1" />);
  fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
  const reject = screen.getAllByRole("button", { name: "Reject" }).find((button) => button.className.includes("button-danger"))!;
  expect(reject).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Reason (required)"), { target: { value: "Wrong supplier" } });
  fireEvent.click(reject);
  await waitFor(() => expect(writes).toEqual([{ path: "/api/v1/procurement/pickup-reports/r1/reject", body: { reason: "Wrong supplier" } }]));
});
