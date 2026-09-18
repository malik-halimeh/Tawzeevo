import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { deleteLocalDatabase, forgetLocalDatabase, getDeviceInstallationId, openLocalDatabase } from "./db";
import { bootstrapLocalProjection, localCustomerBalances, localSyncStatus, searchLocalCustomers } from "./sync";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";

function customer(index: number) {
  return {
    id: `c${index}`.padEnd(36, "0"), tenant_id: tenant, name: `Customer ${index}`, phone: `+9617012345${index}`, phone_raw: null,
    address: null, latitude: null, longitude: null, grade: "A", version: 1, created_at: "2026-09-18T00:00:00Z", updated_at: "2026-09-18T00:00:00Z",
  };
}

interface FetchScript {
  failAtCustomerPage?: number;
  calls: string[];
}

function installFetch(script: FetchScript) {
  let customerPages = 0;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    script.calls.push(`${init?.method ?? "GET"} ${url.pathname}${url.search}`);
    if (url.pathname === "/api/v1/sync/bootstrap" && init?.method === "POST") {
      return Promise.resolve(Response.json({
        device: { id: "device-row", device_installation_id: getDeviceInstallationId(), lease_expires_at: "2026-09-19T00:00:00Z", revoked_at: null },
        high_water_change_seq: 42, protocol_version: 1, app_schema_version: 1,
        collections: ["customers", "tenant_products", "customer_ledger_entries"], page_size: 2,
      }));
    }
    if (url.pathname === "/api/v1/sync/bootstrap/customers") {
      customerPages += 1;
      if (script.failAtCustomerPage === customerPages) return Promise.reject(new TypeError("Failed to fetch"));
      const cursor = url.searchParams.get("cursor");
      if (!cursor) return Promise.resolve(Response.json({ collection: "customers", items: [customer(1), customer(2)], next_cursor: customer(2).id, high_water_change_seq: 42 }));
      return Promise.resolve(Response.json({ collection: "customers", items: [customer(3)], next_cursor: null, high_water_change_seq: 42 }));
    }
    if (url.pathname === "/api/v1/sync/bootstrap/tenant_products") {
      return Promise.resolve(Response.json({ collection: "tenant_products", items: [{ id: "p1".padEnd(36, "0"), tenant_id: tenant, category_id: "cat", master_product_id: null, name: "Cedar Water", is_published: true, unit_price: "12.5000", currency: "USD", price_basis: "PIECE", pieces_per_box: 12, version: 1 }], next_cursor: null, high_water_change_seq: 42 }));
    }
    if (url.pathname === "/api/v1/sync/bootstrap/customer_ledger_entries") {
      return Promise.resolve(Response.json({ collection: "customer_ledger_entries", items: [
        { id: "l1".padEnd(36, "0"), tenant_id: tenant, customer_id: customer(1).id, currency: "USD", signed_amount: "24.2500", entry_type: "INVOICE_CHARGE", source_type: "INVOICE", source_id: null, effective_at: "2026-09-18T00:00:00Z" },
        { id: "l2".padEnd(36, "0"), tenant_id: tenant, customer_id: customer(1).id, currency: "USD", signed_amount: "-10.0000", entry_type: "CUSTOMER_PAYMENT", source_type: "PAYMENT", source_id: null, effective_at: "2026-09-18T01:00:00Z" },
      ], next_cursor: null, high_water_change_seq: 42 }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
}

describe("offline bootstrap", () => {
  beforeEach(async () => { localStorage.clear(); await deleteLocalDatabase(tenant, membership); });
  afterEach(() => { vi.unstubAllGlobals(); });

  test("downloads every collection page by page and records the resume cursor", async () => {
    const script: FetchScript = { calls: [] };
    installFetch(script);
    const status = await bootstrapLocalProjection(tenant, membership);
    expect(status.counts).toEqual({ customers: 3, products: 1, invoices: 0, outbox_pending: 0 });
    expect(status.cursor).toBe(42);
    expect(status.bootstrapped_at).toBeTruthy();
    expect(script.calls.filter((call) => call.includes("/bootstrap/customers"))).toHaveLength(2);
    expect(script.calls[0]).toContain("POST /api/v1/sync/bootstrap");
    const db = openLocalDatabase(tenant, membership);
    expect(await db.meta.get("sync.bootstrap.in_progress")).toBeUndefined();
    expect(await localCustomerBalances(tenant, membership, customer(1).id)).toEqual([{ currency: "USD", balance: "14.2500" }]);
  });

  test("an interrupted download resumes from the last stored page without re-registering", async () => {
    const failing: FetchScript = { calls: [], failAtCustomerPage: 2 };
    installFetch(failing);
    await expect(bootstrapLocalProjection(tenant, membership)).rejects.toThrow("Failed to fetch");
    const db = openLocalDatabase(tenant, membership);
    expect(await db.customers.count()).toBe(2);
    expect((await db.meta.get("sync.bootstrap.cursor.customers"))?.value).toBe(customer(2).id);
    expect((await localSyncStatus(tenant, membership)).bootstrapped_at).toBeNull();

    const resumed: FetchScript = { calls: [] };
    installFetch(resumed);
    const status = await bootstrapLocalProjection(tenant, membership);
    expect(status.counts.customers).toBe(3);
    expect(resumed.calls.some((call) => call.startsWith("POST /api/v1/sync/bootstrap"))).toBe(false);
    expect(resumed.calls.filter((call) => call.includes("/bootstrap/customers"))).toHaveLength(1);
    expect(resumed.calls[0]).toContain(`cursor=${customer(2).id}`);
  });

  test("local phone search works after a browser restart of the same device", async () => {
    installFetch({ calls: [] });
    await bootstrapLocalProjection(tenant, membership);
    const device = getDeviceInstallationId();
    // Simulate a restart: forget the in-memory handle but keep IndexedDB and localStorage.
    forgetLocalDatabase(tenant, membership);
    expect(getDeviceInstallationId()).toBe(device);
    const found = await searchLocalCustomers(tenant, membership, "70 123 452");
    expect(found.map((row) => row.name)).toEqual(["Customer 2"]);
    expect(await searchLocalCustomers(tenant, membership, "0000")).toEqual([]);
  });

  test("two memberships never share a local database", async () => {
    installFetch({ calls: [] });
    await bootstrapLocalProjection(tenant, membership);
    const other = openLocalDatabase("33333333-3333-4333-8333-333333333333", membership);
    expect(await other.customers.count()).toBe(0);
    expect(await openLocalDatabase(tenant, membership).customers.count()).toBe(3);
  });
});
