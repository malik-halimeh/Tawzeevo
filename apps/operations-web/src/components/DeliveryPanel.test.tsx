import { cleanup, fireEvent, render as renderBare, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { DeliveryPanel } from "./DeliveryPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

/** Delivery entries link to their invoice, so the panel renders inside a router. */
const render = (ui: ReactElement) => renderBare(<MemoryRouter>{ui}</MemoryRouter>);

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
    if (path.endsWith("/memberships")) return Promise.resolve(Response.json({ members: [{ id: "m1", role: "owner", is_active: true, display_name: "Layla Haddad", email: "l@example.com", is_self: true, created_at: "", revoked_at: null }] }));
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
  fireEvent.click(screen.getByRole("button", { name: "Yes, mark delivered" })); // a final action asks once
  expect(await screen.findByText("Delivery marked done.")).toBeInTheDocument();
  expect(bodies.find((b) => "expected_version" in b)).toEqual({ expected_version: 1, note: null });
});

test("opened for an invoice: it is preselected when deliverable, unknown ids are ignored, and entries link to their invoice", async () => {
  await i18n.changeLanguage("en");
  const bodies: Record<string, unknown>[] = [];
  const listed: string[] = [];
  const done = { ...baseTask, id: "t9", invoice_id: "inv9", official_invoice_number: "2026-000009", status: "COMPLETED" };
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    const path = url.split("?")[0]!;
    if (typeof init?.body === "string") bodies.push(JSON.parse(init.body) as Record<string, unknown>);
    if (path.endsWith("/delivery-tasks") && init?.method === "POST") return Promise.resolve(Response.json({ ...baseTask }, { status: 201 }));
    if (path.endsWith("/delivery-tasks")) { listed.push(url); return Promise.resolve(Response.json({ tasks: [done], eligible_members: [me], sole_operator: true })); }
    if (path.endsWith("/memberships")) return Promise.resolve(Response.json({ members: [] }));
    if (path.endsWith("/eligible-invoices")) return Promise.resolve(Response.json({ invoices: [{ invoice_id: "inv1", official_invoice_number: "2026-000001", customer_id: "c1", customer_name: "Corner Shop", currency: "USD", net_sales: "30.0000", confirmed_at: "2026-09-19T05:00:00Z", order_id: null, delivery_date: null }] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<DeliveryPanel focusInvoiceId="inv1" tenantId="t1" />);
  await waitFor(() => expect(screen.getByLabelText("Confirmed invoice")).toHaveValue("inv1"));
  expect(listed[0]).not.toContain("status="); // every state, so the invoice's delivery is found
  fireEvent.click(screen.getByRole("button", { name: "Create delivery" }));
  expect(await screen.findByText("Delivery created.")).toBeInTheDocument();
  expect(bodies[0]).toEqual({ invoice_id: "inv1", assigned_membership_id: null, delivery_date: null }); // same command as by hand
  expect(screen.getByRole("link", { name: "Open invoice 2026-000009" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=inv9");

  cleanup();
  render(<DeliveryPanel focusInvoiceId="not-ours" tenantId="t1" />);
  expect(await screen.findByRole("option", { name: /2026-000001/ })).toBeInTheDocument();
  expect(screen.getByLabelText("Confirmed invoice")).toHaveValue("");
});

test("each delivery row has its own completion note, cancel reason and date/notes edit", async () => {
  await i18n.changeLanguage("en");
  const sent: Array<{ path: string; method: string; body: Record<string, unknown> }> = [];
  const other = { ...baseTask, id: "t2", customer_name: "Hill Market", invoice_id: "inv2", notes: "Back door", version: 3 };
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    const method = init?.method ?? "GET";
    if (typeof init?.body === "string") sent.push({ path, method, body: JSON.parse(init.body) as Record<string, unknown> });
    if (path.endsWith("/delivery-tasks") && method === "GET") return Promise.resolve(Response.json({ tasks: [baseTask, other], eligible_members: [me], sole_operator: true }));
    if (path.endsWith("/memberships")) return Promise.resolve(Response.json({ members: [] }));
    if (path.endsWith("/eligible-invoices")) return Promise.resolve(Response.json({ invoices: [] }));
    if (method !== "GET") return Promise.resolve(Response.json(baseTask));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<DeliveryPanel tenantId="t1" />);
  const row = (name: string) => screen.getByText(name).closest("li")!;
  await screen.findByText("Hill Market");
  expect(screen.queryByLabelText(/Note \/ reason/)).not.toBeInTheDocument(); // no field shared by every row

  // Cancelling asks for this row's reason and sends only it.
  fireEvent.click(within(row("Corner Shop")).getByRole("button", { name: "Cancel delivery" }));
  const confirmCancel = within(row("Corner Shop")).getByRole("button", { name: "Yes, cancel delivery" });
  expect(confirmCancel).toBeDisabled();
  fireEvent.change(within(row("Corner Shop")).getByLabelText("Reason for cancelling"), { target: { value: "Shop closed" } });
  fireEvent.click(confirmCancel);
  expect(await screen.findByText("Delivery cancelled.")).toBeInTheDocument();
  expect(sent.at(-1)).toEqual({ path: "/api/v1/delivery-tasks/t1/cancel", method: "POST", body: { expected_version: 1, reason: "Shop closed" } });

  // Completing another row starts with an empty note: nothing typed elsewhere travels with it.
  fireEvent.click(within(row("Hill Market")).getByRole("button", { name: "Mark delivered" }));
  expect(within(row("Hill Market")).getByLabelText("Note (optional)")).toHaveValue("");
  fireEvent.click(within(row("Hill Market")).getByRole("button", { name: "Back" }));
  expect(within(row("Hill Market")).queryByRole("button", { name: "Yes, mark delivered" })).not.toBeInTheDocument();

  // Edit changes the date through the existing update with the version this screen saw.
  fireEvent.click(within(row("Hill Market")).getByRole("button", { name: "Edit" }));
  const form = screen.getByRole("form", { name: "Edit delivery for Hill Market" });
  expect(within(form).getByLabelText("Delivery notes")).toHaveValue("Back door");
  fireEvent.change(within(form).getByLabelText("Delivery date"), { target: { value: "2026-09-30" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save changes" }));
  expect(await screen.findByText("Delivery updated.")).toBeInTheDocument();
  expect(sent.at(-1)).toEqual({ path: "/api/v1/delivery-tasks/t2", method: "PATCH", body: { expected_version: 3, delivery_date: "2026-09-30" } });
});

test("open deliveries get one stop order per assignee, with the stop number and a map link", async () => {
  await i18n.changeLanguage("en");
  const driver = { membership_id: "m2", role: "driver", display_name: "Karim Saad", is_self: false };
  const bodies: Record<string, unknown>[] = [];
  const tasks = [
    { ...baseTask, id: "t1", customer_name: "Hamra Shop", customer_latitude: "33.896600", customer_longitude: "35.482300", route_sequence: 2 },
    { ...baseTask, id: "t2", customer_name: "Jounieh Shop", assignee: driver },
    { ...baseTask, id: "t3", customer_name: "Done Shop", status: "COMPLETED" },
  ];
  vi.stubGlobal("navigator", { ...navigator, geolocation: undefined });
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    if (typeof init?.body === "string") bodies.push(JSON.parse(init.body) as Record<string, unknown>);
    if (path.endsWith("/delivery-tasks")) return Promise.resolve(Response.json({ tasks, eligible_members: [me, driver], sole_operator: false }));
    if (path.endsWith("/memberships")) return Promise.resolve(Response.json({ members: [] }));
    if (path.endsWith("/eligible-invoices")) return Promise.resolve(Response.json({ invoices: [] }));
    if (path.endsWith("/routes/suggest-order")) return Promise.resolve(Response.json({ method: "openrouteservice", note: null, stops: [{ task_id: "t2", sequence: 1, customer_name: "Jounieh Shop", latitude: null, longitude: null, has_location: false }], unlocated_task_ids: ["t2"] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<DeliveryPanel tenantId="t1" />);
  expect(await screen.findByRole("heading", { name: "Stop order for Layla Haddad · owner (me)" })).toBeInTheDocument();
  const driverRoute = screen.getByRole("heading", { name: "Stop order for Karim Saad · driver" });
  expect(screen.getAllByRole("heading", { name: /^Stop order for/ })).toHaveLength(2); // closed deliveries are never routed
  expect(screen.queryByRole("button", { name: "Suppliers near me" })).not.toBeInTheDocument(); // field tools stay on My route
  expect(screen.getByText(/Stop 02/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open in maps" })).toHaveAttribute("href", "https://www.google.com/maps?q=33.896600,35.482300");
  expect(screen.getAllByText("No saved location").length).toBeGreaterThan(0);
  fireEvent.click(driverRoute.parentElement!.querySelector("button")!);
  expect(await screen.findByText("Road route from OpenRouteService")).toBeInTheDocument();
  expect(bodies[0]).toEqual({ origin: null, task_ids: ["t2"] }); // only that driver's open deliveries
});

test("with drivers, the driver chosen last on this device starts selected in the create form (D-103)", async () => {
  await i18n.changeLanguage("en");
  localStorage.setItem("tawzeevo.last.driver.t1", "m2");
  const driver = { membership_id: "m2", role: "driver", display_name: "Karim", is_self: false };
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    if (typeof init?.body === "string") bodies.push(JSON.parse(init.body) as Record<string, unknown>);
    if (path.endsWith("/delivery-tasks") && init?.method === "POST") return Promise.resolve(Response.json({ ...baseTask, assignee: driver }, { status: 201 }));
    if (path.endsWith("/delivery-tasks")) return Promise.resolve(Response.json({ tasks: [], eligible_members: [me, driver], sole_operator: false }));
    if (path.endsWith("/memberships")) return Promise.resolve(Response.json({ members: [] }));
    if (path.endsWith("/eligible-invoices")) return Promise.resolve(Response.json({ invoices: [{ invoice_id: "inv1", official_invoice_number: "2026-000001", customer_id: "c1", customer_name: "Corner Shop", currency: "USD", net_sales: "30.0000", confirmed_at: "2026-09-19T05:00:00Z", order_id: null, delivery_date: null }] }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
  render(<DeliveryPanel tenantId="t1" />);
  await waitFor(() => expect(screen.getByLabelText("Deliver by")).toHaveValue("m2"));
  fireEvent.change(screen.getByLabelText("Confirmed invoice"), { target: { value: "inv1" } });
  fireEvent.click(screen.getByRole("button", { name: "Create delivery" }));
  expect(await screen.findByText("Delivery created.")).toBeInTheDocument();
  expect(bodies[0]).toMatchObject({ assigned_membership_id: "m2" });
  localStorage.clear();
});
