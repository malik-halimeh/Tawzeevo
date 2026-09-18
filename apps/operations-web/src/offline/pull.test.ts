import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { deleteLocalDatabase, openLocalDatabase } from "./db";
import { createCustomerOffline, listOutbox } from "./outbox";
import { pullChanges, quarantineAndPurge, syncNow } from "./pull";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";
const c1 = "c1".padEnd(36, "0");
const b1 = "b1".padEnd(36, "0");

function change(seq: number, entity_type: string, entity_id: string, operation: "upsert" | "delete", payload: Record<string, unknown>) {
  return { change_seq: seq, entity_type, entity_id, operation, version: 1, payload, operation_id: null, device_installation_id: null, occurred_at: "2026-09-18T00:00:00Z" };
}

interface Script {
  pull?: (cursor: number) => { status: number; body: unknown };
  push?: () => { status: number; body: unknown };
  bootstrap?: boolean;
  calls: string[];
}

function install(script: Script) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString());
    script.calls.push(`${init?.method ?? "GET"} ${url.pathname}${url.search}`);
    if (url.pathname === "/api/v1/sync/pull" && script.pull) {
      const { status, body } = script.pull(Number(url.searchParams.get("cursor")));
      return Promise.resolve(Response.json(body, { status }));
    }
    if (url.pathname === "/api/v1/sync/push" && script.push) {
      const { status, body } = script.push();
      return Promise.resolve(Response.json(body, { status }));
    }
    if (script.bootstrap && url.pathname === "/api/v1/sync/bootstrap") {
      return Promise.resolve(Response.json({ device: { id: "d", device_installation_id: "x", lease_expires_at: "2026-09-19T00:00:00Z", revoked_at: null }, high_water_change_seq: 500, protocol_version: 1, app_schema_version: 1, collections: ["customers"], page_size: 100 }));
    }
    if (script.bootstrap && url.pathname === "/api/v1/sync/bootstrap/customers") {
      return Promise.resolve(Response.json({ collection: "customers", items: [{ id: c1, tenant_id: tenant, name: "Rebootstrapped", phone: "+96170123456", phone_raw: null, address: null, latitude: null, longitude: null, grade: null, version: 3, created_at: "", updated_at: "" }], next_cursor: null, high_water_change_seq: 500 }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
}

describe("incremental pull and sync", () => {
  beforeEach(async () => { localStorage.clear(); await deleteLocalDatabase(tenant, membership); });
  afterEach(() => { vi.unstubAllGlobals(); });

  test("applies upserts and tombstones page by page and advances the cursor per page", async () => {
    const db = openLocalDatabase(tenant, membership);
    await db.barcodes.put({ id: b1, tenant_id: tenant, tenant_product_id: "p", barcode: "528", package_level: "PIECE" });
    await db.meta.put({ key: "sync.cursor", value: "10" });
    const script: Script = { calls: [], pull: (cursor) => cursor === 10
      ? { status: 200, body: { changes: [change(11, "customer", c1, "upsert", { id: c1, tenant_id: tenant, name: "Maya", phone: "+96170123456", version: 1 }), change(12, "tenant_barcode", b1, "delete", { id: b1 })], next_cursor: 12, high_water_change_seq: 13, has_more: true, protocol_version: 1 } }
      : { status: 200, body: { changes: [change(13, "customer", c1, "upsert", { id: c1, tenant_id: tenant, name: "Maya Edited", phone: "+96170123456", version: 2 })], next_cursor: 13, high_water_change_seq: 13, has_more: false, protocol_version: 1 } } };
    install(script);
    const summary = await pullChanges(tenant, membership);
    expect(summary).toEqual({ applied: 3, pages: 2, cursor: 13, rebootstrapped: false });
    expect((await db.customers.get(c1))?.name).toBe("Maya Edited");
    expect(await db.barcodes.get(b1)).toBeUndefined();
    expect((await db.meta.get("sync.cursor"))?.value).toBe("13");
    expect(script.calls.filter((call) => call.includes("/pull")).map((call) => call.split("cursor=")[1])).toEqual(["10", "12"]);
  });

  test("a cursor below the retention floor triggers a re-bootstrap that keeps the outbox", async () => {
    await createCustomerOffline(tenant, membership, { name: "Queued", phone: "+96170123400" });
    const db = openLocalDatabase(tenant, membership);
    await db.meta.put({ key: "sync.cursor", value: "1" });
    install({ calls: [], bootstrap: true, pull: () => ({ status: 410, body: { detail: { code: "SYNC_REBOOTSTRAP_REQUIRED", message: "bootstrap again" } } }) });
    const summary = await pullChanges(tenant, membership);
    expect(summary.rebootstrapped).toBe(true);
    expect(summary.cursor).toBe(500);
    expect((await db.customers.get(c1))?.name).toBe("Rebootstrapped");
    expect((await listOutbox(tenant, membership)).map((row) => row.state)).toEqual(["pending"]);
  });

  test("syncNow pushes then pulls, and a revoked device is quarantined and purged", async () => {
    await createCustomerOffline(tenant, membership, { name: "Queued", phone: "+96170123400" });
    const okScript: Script = { calls: [], push: () => ({ status: 200, body: { results: [], high_water_change_seq: 5 } }), pull: () => ({ status: 200, body: { changes: [], next_cursor: 5, high_water_change_seq: 5, has_more: false, protocol_version: 1 } }) };
    install(okScript);
    const outcome = await syncNow(tenant, membership);
    expect(outcome.kind).toBe("ok");
    expect(okScript.calls[0]).toContain("POST /api/v1/sync/push");
    expect(okScript.calls[1]).toContain("GET /api/v1/sync/pull");

    await createCustomerOffline(tenant, membership, { name: "Late", phone: "+96170123401" });
    install({ calls: [], push: () => ({ status: 403, body: { detail: { code: "SYNC_DEVICE_REVOKED", message: "revoked" } } }) });
    const revoked = await syncNow(tenant, membership);
    expect(revoked).toEqual({ kind: "revoked", reason: "SYNC_DEVICE_REVOKED" });
    const fresh = openLocalDatabase(tenant, membership);
    expect(await fresh.customers.count()).toBe(0);
    expect(await fresh.outbox.count()).toBe(0);
    const quarantine = JSON.parse(localStorage.getItem(`tawzeevo.quarantine.${tenant}.${membership}`) ?? "[]") as Array<{ reason: string }>;
    expect(quarantine.some((row) => row.reason === "SYNC_DEVICE_REVOKED")).toBe(true);
  });

  test("offline sync attempts report offline instead of failing", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await createCustomerOffline(tenant, membership, { name: "Queued", phone: "+96170123400" });
    expect(await syncNow(tenant, membership)).toEqual({ kind: "offline" });
    expect((await listOutbox(tenant, membership))[0]?.state).toBe("retryable_failed");
    await quarantineAndPurge(tenant, membership, "TEST");
    expect(await openLocalDatabase(tenant, membership).outbox.count()).toBe(0);
  });
});
