import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OrdersPanel } from "./OrdersPanel";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const order = {
  id: "o1", status: "RECEIVED", contact_name: "Rami", contact_phone: "+96170000001", contact_address: "Tripoli", notes: null, currency: "USD",
  intended_customer_id: null, intended_assurance: null, linked_customer_id: "c1", invoice_id: "inv1", delivery_date: null,
  decision_note: null, created_at: "2026-09-19T00:00:00Z", decided_at: null,
};
const invoice = { id: "inv1", status: "DRAFT", current_revision_id: "rev-3", official_invoice_number: null, net_sales: "8.50", currency: "USD", items: [] };

/** Records every write in order; `failTask` makes the delivery creation refuse. */
function stub({ sole, failTask = false }: { sole: boolean; failTask?: boolean }) {
  const writes: Array<{ method: string; path: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost");
    const method = init?.method ?? "GET";
    if (method !== "GET") {
      writes.push({ method, path: url.pathname, body: JSON.parse(typeof init?.body === "string" ? init.body : "{}") });
      if (failTask && url.pathname === "/api/v1/delivery-tasks") return Promise.resolve(Response.json({ detail: { code: "INVOICE_NOT_ELIGIBLE", message: "Invoice cannot be delivered" } }, { status: 409 }));
      return Promise.resolve(Response.json({}));
    }
    if (url.pathname === "/api/v1/delivery-tasks") return Promise.resolve(Response.json({ tasks: [], sole_operator: sole, eligible_members: [{ membership_id: "m1", role: "owner", display_name: "Layla", is_self: true }, { membership_id: "m2", role: "driver", display_name: "Karim", is_self: false }] }));
    if (url.pathname.endsWith("/orders")) return Promise.resolve(Response.json({ orders: [order] }));
    if (url.pathname.endsWith("/orders/o1")) return Promise.resolve(Response.json({ order, invoice, candidates: [], cancellation_requests: [], linked_customer_name: "Rami Store" }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><OrdersPanel orderId="o1" tenantId="t1" /></MemoryRouter></QueryClientProvider>);
  return writes;
}

test("confirm and schedule runs the same three steps in order: confirm, delivery date, delivery", async () => {
  const writes = stub({ sole: true });
  const form = await screen.findByRole("form", { name: "Confirm and schedule" });
  expect(within(form).queryByLabelText("Deliver by")).not.toBeInTheDocument(); // a sole owner is the assignee
  fireEvent.change(within(form).getByLabelText("Delivery date"), { target: { value: "2026-09-30" } });
  fireEvent.click(within(form).getByRole("button", { name: "Confirm and schedule" }));
  expect(await screen.findByText("Order confirmed, the delivery date saved and the delivery created.")).toBeInTheDocument();
  expect(writes).toEqual([
    { method: "POST", path: "/api/v1/tenants/t1/orders/o1/confirm", body: { expected_revision_id: "rev-3" } },
    { method: "PUT", path: "/api/v1/tenants/t1/orders/o1/delivery-date", body: { delivery_date: "2026-09-30" } },
    { method: "POST", path: "/api/v1/delivery-tasks", body: { invoice_id: "inv1", assigned_membership_id: null, delivery_date: "2026-09-30" } },
  ]);
});

test("with drivers the assignee is chosen, and a failed later step is named while the order stays confirmed", async () => {
  const writes = stub({ sole: false, failTask: true });
  const form = await screen.findByRole("form", { name: "Confirm and schedule" });
  fireEvent.change(await within(form).findByLabelText("Deliver by"), { target: { value: "m2" } });
  fireEvent.click(within(form).getByRole("button", { name: "Confirm and schedule" }));
  expect(await screen.findByText("Order confirmed, but creating the delivery did not complete. The invoice stays confirmed; finish that step below.")).toBeInTheDocument();
  expect(screen.getByText("Invoice cannot be delivered")).toBeInTheDocument();
  expect(writes.map((write) => write.path)).toEqual(["/api/v1/tenants/t1/orders/o1/confirm", "/api/v1/delivery-tasks"]); // no date given: none saved
  await waitFor(() => expect(writes[1]?.body).toEqual({ invoice_id: "inv1", assigned_membership_id: "m2", delivery_date: null }));
});

test("without creating the delivery, only the confirmation is sent", async () => {
  const writes = stub({ sole: true });
  const form = await screen.findByRole("form", { name: "Confirm and schedule" });
  fireEvent.click(within(form).getByLabelText("Create the delivery now"));
  fireEvent.click(within(form).getByRole("button", { name: "Confirm and schedule" }));
  expect(await screen.findByText("Order confirmed; the invoice is now official.")).toBeInTheDocument();
  expect(writes.map((write) => write.path)).toEqual(["/api/v1/tenants/t1/orders/o1/confirm"]);
});

test("the driver chosen last on this device starts selected, and a choice no longer offered is ignored (D-103)", async () => {
  localStorage.setItem("tawzeevo.last.driver.t1", "m2");
  let writes = stub({ sole: false });
  let form = await screen.findByRole("form", { name: "Confirm and schedule" });
  await waitFor(() => expect(within(form).getByLabelText("Deliver by")).toHaveValue("m2"));
  fireEvent.click(within(form).getByRole("button", { name: "Confirm and schedule" }));
  await waitFor(() => expect(writes.some((write) => write.path === "/api/v1/delivery-tasks")).toBe(true));
  expect(writes.find((write) => write.path === "/api/v1/delivery-tasks")?.body).toMatchObject({ assigned_membership_id: "m2" });

  cleanup();
  localStorage.setItem("tawzeevo.last.driver.t1", "someone-gone");
  writes = stub({ sole: false });
  form = await screen.findByRole("form", { name: "Confirm and schedule" });
  expect(await within(form).findByLabelText("Deliver by")).toHaveValue("");
  fireEvent.change(within(form).getByLabelText("Deliver by"), { target: { value: "m1" } });
  fireEvent.click(within(form).getByRole("button", { name: "Confirm and schedule" }));
  await waitFor(() => expect(localStorage.getItem("tawzeevo.last.driver.t1")).toBe("m1"));
  localStorage.clear();
});
