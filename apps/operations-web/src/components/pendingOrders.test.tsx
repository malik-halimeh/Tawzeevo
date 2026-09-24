import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { clearSession } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import i18n from "../i18n";
import { AppShell } from "./AppShell";
import { type PendingOrder, newArrivals, titleWithCount } from "./pendingOrders";

const order = (id: string, name: string): PendingOrder => ({ id, contact_name: name, created_at: "2026-09-24T08:00:00Z" });

describe("pending-order helpers", () => {
  test("the first answer is only a baseline; later answers report orders that were not there", () => {
    expect(newArrivals(null, [order("a", "A")])).toEqual([]);
    expect(newArrivals(new Set(["a"]), [order("a", "A"), order("b", "B")]).map((row) => row.id)).toEqual(["b"]);
    expect(newArrivals(new Set(["a", "b"]), [order("b", "B")])).toEqual([]); // a decided order is no arrival
  });

  test("the tab title carries the count only while orders await review", () => {
    expect(titleWithCount("Tawzeevo Operations", 3)).toBe("(3) Tawzeevo Operations");
    expect(titleWithCount("Tawzeevo Operations", 0)).toBe("Tawzeevo Operations");
  });
});

describe("owner shell: Orders badge, tab title and new-order notice", () => {
  const tenantId = "44444444-4444-4444-4444-444444444444";
  let pending: PendingOrder[] = [];
  let queryClient: QueryClient;
  const polled: string[] = [];

  beforeEach(async () => {
    clearSession();
    await i18n.changeLanguage("en");
    document.title = "Tawzeevo Operations";
    pending = [order("o1", "Rami Store")];
    polled.length = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = input instanceof Request ? input.url : input.toString();
      const reply = (body: unknown) => Promise.resolve(Response.json(body));
      if (url.endsWith("/api/v1/auth/refresh")) return reply({ access_token: "token", token_type: "bearer", expires_in: 900 });
      if (url.endsWith("/users/me")) return reply({ id: "u1", first_name: "Nour", last_name: "Owner", email: "nour@example.com", phone: "+96170123456", city: "Beirut", age: 34, type: "client", created_at: "2026-08-20T08:00:00Z", updated_at: "2026-08-20T08:00:00Z" });
      if (url.endsWith("/api/v1/tenant-contexts")) return reply({ tenants: [{ membership_id: "m1", tenant_id: tenantId, tenant_name: "North Route", tenant_status: "ACTIVE", role: "owner" }] });
      if (url.includes(`/api/v1/tenants/${tenantId}/orders`) && url.includes("status=RECEIVED")) { polled.push(url); return reply({ orders: pending }); }
      return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
    }));
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/workspace?section=invoices"]}>
          <AuthProvider>
            <Routes><Route element={<AppShell />}><Route element={<p>Invoices body</p>} path="/workspace" /></Route></Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  const rail = () => screen.getByRole("navigation", { name: "Workspace navigation" });
  const poll = () => act(async () => { await queryClient.refetchQueries({ queryKey: ["pending-orders"] }); });

  test("counts orders awaiting review on another page, notices only new ones, and follows decisions", async () => {
    // First answer: badge and title, but no notice for an order that already existed.
    expect(await within(rail()).findByText("1 awaiting review")).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("(1) Tawzeevo Operations"));
    expect(screen.queryByText(/New order from/)).not.toBeInTheDocument();
    expect(polled[0]).toContain(`tenant_id=${tenantId}`);

    // One new order: a notice naming the customer, linking to that order.
    pending = [order("o1", "Rami Store"), order("o2", "Lina Market")];
    await poll();
    const single = await screen.findByRole("link", { name: "New order from Lina Market" });
    expect(single).toHaveAttribute("href", "/workspace?section=orders&order=o2");
    expect(document.title).toBe("(2) Tawzeevo Operations");
    expect(within(rail()).getByText("2 awaiting review")).toBeInTheDocument();

    // Several at once: one notice with the count, linking to Orders.
    pending = [order("o1", "Rami Store"), order("o2", "Lina Market"), order("o3", "C"), order("o4", "D")];
    await poll();
    const several = await screen.findByRole("link", { name: "2 new orders" });
    expect(several.getAttribute("href")).toBe("/workspace?section=orders");

    // The owner decided every order: the badge and the title prefix go.
    pending = [];
    await poll();
    await waitFor(() => expect(document.title).toBe("Tawzeevo Operations"));
    expect(within(rail()).queryByText(/awaiting review/)).not.toBeInTheDocument();
  });
});
