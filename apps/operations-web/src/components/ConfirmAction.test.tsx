import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OrdersPanel } from "./OrdersPanel";
import { StorefrontSettings } from "./StorefrontSettings";
import { ConfirmAction } from "./Ui";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("a confirm action runs only after its confirm button, and Keep runs nothing", async () => {
  const onConfirm = vi.fn();
  render(<ConfirmAction confirmLabel="Yes, remove" label="Remove" onConfirm={onConfirm}>This cannot be undone.</ConfirmAction>);
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(screen.getByText("This cannot be undone.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Yes, remove" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Keep" }));
  expect(onConfirm).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.getByRole("button", { name: "Remove" })).toHaveFocus());

  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, remove" }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
});

test("declining an order and approving a cancellation each ask once before anything is sent", async () => {
  const order = {
    id: "o1", status: "RECEIVED", contact_name: "Rami", contact_phone: "+96170000001", contact_address: "Tripoli", notes: null, currency: "USD",
    intended_customer_id: null, intended_assurance: null, linked_customer_id: "c1", invoice_id: "inv1", delivery_date: null,
    decision_note: null, created_at: "2026-09-19T00:00:00Z", decided_at: null,
  };
  const invoice = { id: "inv1", status: "DRAFT", current_revision_id: "rev-1", official_invoice_number: null, net_sales: "8.50", currency: "USD", items: [] };
  const request = { id: "r1", order_id: "o1", status: "PENDING", reason: "Ordered twice", created_at: "2026-09-19T02:00:00Z", decided_at: null, decision_note: null };
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    if (init?.method === "POST") { posts.push(path); return Promise.resolve(Response.json({})); }
    if (path.endsWith("/orders")) return Promise.resolve(Response.json({ orders: [order] }));
    if (path.endsWith("/orders/o1")) return Promise.resolve(Response.json({ order, invoice, candidates: [], cancellation_requests: [request], linked_customer_name: "Rami Store" }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><OrdersPanel orderId="o1" tenantId="t1" /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Decline order" }));
  fireEvent.click(screen.getByRole("button", { name: "Keep" }));
  fireEvent.click(screen.getByRole("button", { name: "Approve cancellation" }));
  expect(posts).toEqual([]);
  fireEvent.click(screen.getByRole("button", { name: "Yes, approve and reverse the sale" }));
  await waitFor(() => expect(posts).toEqual(["/api/v1/tenants/t1/orders/cancellation-requests/r1/decide"]));
  fireEvent.click(await screen.findByRole("button", { name: "Decline order" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, decline order" }));
  await waitFor(() => expect(posts).toContain("/api/v1/tenants/t1/orders/o1/decline"));
});

test("a storefront access policy change is staged and applied only after it is confirmed", async () => {
  const puts: Array<Record<string, unknown>> = [];
  const settings = { slug: "cedar", previous_slugs: [], published_products: 3, accepting_orders: true, customer_access_policy: "LINK" };
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    if (init?.method === "PUT" && path.endsWith("/access-policy")) {
      const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>;
      puts.push(body);
      return Promise.resolve(Response.json({ ...settings, customer_access_policy: body.policy }));
    }
    if (path.endsWith("/storefront")) return Promise.resolve(Response.json(settings));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<StorefrontSettings tenantId="t1" />);
  const policy = await screen.findByRole("combobox", { name: "Customer access policy" });
  fireEvent.change(policy, { target: { value: "VERIFIED" } });
  expect(screen.getByText(/Change customer access to Verified phone/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Keep" }));
  expect(policy).toHaveValue("LINK");
  expect(puts).toEqual([]);

  fireEvent.change(policy, { target: { value: "VERIFIED" } });
  fireEvent.click(screen.getByRole("button", { name: "Yes, change policy" }));
  await waitFor(() => expect(puts).toEqual([{ policy: "VERIFIED" }]));
  expect(await screen.findByText(/Access policy is now/)).toBeInTheDocument();
});
