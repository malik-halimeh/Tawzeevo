import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { DeliveryPanel } from "./DeliveryPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const me = { membership_id: "m1", role: "owner", display_name: "Layla Haddad", is_self: true };
const baseTask = { id: "t1", status: "ASSIGNED", invoice_id: "inv1", official_invoice_number: "2026-000001", order_id: null, customer_id: "c1", customer_name: "Corner Shop", customer_phone: "+96170000001", customer_address: "Hamra", customer_latitude: null, customer_longitude: null, assignee: me, delivery_date: "2026-09-20", route_sequence: null, currency: "USD", amount_to_collect: "30.0000", items: [{ product_name: "Labneh", quantity: "3.0000", price_basis: "PIECE", pieces_per_box: null }], notes: null, completed_at: null, performed_by: null, completion_note: null, cancelled_at: null, cancel_reason: null, version: 1, created_at: "2026-09-19T06:00:00Z" };

test("sole owner creates a delivery for a confirmed invoice with no driver setup and marks it done", async () => {
  await i18n.changeLanguage("en");
  const tasks: Record<string, unknown>[] = [];
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    if (body) bodies.push(body);
    if (path.endsWith("/delivery-tasks") && init?.method === "POST") { tasks.push({ ...baseTask }); return Promise.resolve(Response.json(tasks[0], { status: 201 })); }
    if (path.endsWith("/delivery-tasks")) return Promise.resolve(Response.json({ tasks, eligible_members: [me], sole_operator: true }));
    if (path.endsWith("/eligible-invoices")) return Promise.resolve(Response.json({ invoices: tasks.length ? [] : [{ invoice_id: "inv1", official_invoice_number: "2026-000001", customer_id: "c1", customer_name: "Corner Shop", currency: "USD", net_sales: "30.0000", confirmed_at: "2026-09-19T05:00:00Z", order_id: null, delivery_date: null }] }));
    if (path.endsWith("/t1/complete")) { tasks[0] = { ...baseTask, status: "COMPLETED", performed_by: me, completed_at: "2026-09-19T07:00:00Z", version: 2 }; return Promise.resolve(Response.json(tasks[0])); }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<DeliveryPanel tenantId="t1" />);
  expect(await screen.findByText("My deliveries")).toBeInTheDocument(); // sole-operator wording
  expect(screen.queryByLabelText("Deliver by")).not.toBeInTheDocument(); // no driver setup demanded
  fireEvent.change(screen.getByLabelText("Confirmed invoice"), { target: { value: "inv1" } });
  fireEvent.click(screen.getByRole("button", { name: "Create delivery" }));
  expect(await screen.findByText("Delivery created.")).toBeInTheDocument();
  expect(bodies[0]).toEqual({ invoice_id: "inv1", assigned_membership_id: null, delivery_date: null });
  expect(await screen.findByText(/Corner Shop/)).toBeInTheDocument();
  expect(screen.getByText(/30\.0000 USD/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mark delivered" }));
  expect(await screen.findByText("Delivery marked done.")).toBeInTheDocument();
  expect(bodies.find((b) => "expected_version" in b)).toEqual({ expected_version: 1, note: null });
});
