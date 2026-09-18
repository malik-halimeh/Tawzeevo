import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { deleteLocalDatabase, forgetLocalDatabase, getDeviceInstallationId, openLocalDatabase } from "./db";
import {
  MAX_ATTEMPTS,
  acceptServerVersion,
  createCustomerOffline,
  flushOutbox,
  listOutbox,
  retryDeadLetters,
  retryWithServerVersion,
  updateCustomerOffline,
} from "./outbox";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";

type Op = { operation_id: string; entity_type: string; operation_type: string; entity_id: string; expected_version: number | null; payload: Record<string, unknown> };
type Mode = "applied" | "conflict" | "reject" | "network" | "server-error" | "protocol-mismatch";

function installPush(mode: Mode, seen: Op[][]) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    if (!url.includes("/api/v1/sync/push")) return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as { operations: Op[]; device_installation_id: string };
    expect(body.device_installation_id).toBe(getDeviceInstallationId());
    seen.push(body.operations);
    if (mode === "network") return Promise.reject(new TypeError("Failed to fetch"));
    if (mode === "server-error") return Promise.resolve(Response.json({ detail: { code: "DOWN", message: "maintenance" } }, { status: 503 }));
    if (mode === "protocol-mismatch") return Promise.resolve(Response.json({ detail: { code: "SYNC_PROTOCOL_MISMATCH", message: "update the app" } }, { status: 409 }));
    return Promise.resolve(Response.json({
      high_water_change_seq: 99,
      results: body.operations.map((op) => {
        if (mode === "reject") return { operation_id: op.operation_id, status: "rejected", replayed: false, entity_type: op.entity_type, entity_id: op.entity_id, version: null, projection: null, error: { code: "INVALID_PHONE", message: "Customer phone is invalid" }, conflict: null };
        if (mode === "conflict") return { operation_id: op.operation_id, status: "conflict", replayed: false, entity_type: op.entity_type, entity_id: op.entity_id, version: 5, projection: null, error: null, conflict: { entity_type: op.entity_type, entity_id: op.entity_id, server_version: 5, client_expected_version: op.expected_version, server_projection: { id: op.entity_id, tenant_id: tenant, name: "Server Name", phone: "+96170123456", phone_raw: null, address: "Server St", latitude: null, longitude: null, grade: "A", version: 5, created_at: "", updated_at: "" }, request_id: "req" } };
        return { operation_id: op.operation_id, status: "applied", replayed: false, entity_type: op.entity_type, entity_id: op.entity_id, version: (op.expected_version ?? 0) + 1, projection: { id: op.entity_id, tenant_id: tenant, name: typeof op.payload.name === "string" ? op.payload.name : "Server Name", phone: "+96170123456", phone_raw: null, address: (op.payload.address as string | null) ?? null, latitude: null, longitude: null, grade: null, version: (op.expected_version ?? 0) + 1, created_at: "", updated_at: "" }, error: null, conflict: null };
      }),
    }));
  }));
}

describe("device outbox", () => {
  beforeEach(async () => { localStorage.clear(); await deleteLocalDatabase(tenant, membership); });
  afterEach(() => { vi.unstubAllGlobals(); });

  test("a local create and its command are written together and acknowledged once", async () => {
    const seen: Op[][] = [];
    installPush("applied", seen);
    const created = await createCustomerOffline(tenant, membership, { name: "Offline Maya", phone: "+96170123456" });
    const db = openLocalDatabase(tenant, membership);
    expect(await db.customers.get(created.id)).toMatchObject({ name: "Offline Maya", version: 1 });
    expect((await listOutbox(tenant, membership)).map((row) => row.state)).toEqual(["pending"]);

    const summary = await flushOutbox(tenant, membership);
    expect(summary).toMatchObject({ sent: 1, acknowledged: 1, conflicts: 0, rejected: 0, failed: 0, high_water_change_seq: 99 });
    expect((await listOutbox(tenant, membership))[0]?.state).toBe("acknowledged");
    expect(seen[0]?.[0]?.entity_id).toBe(created.id);
    // Nothing left to send: a second flush is a no-op.
    expect((await flushOutbox(tenant, membership)).sent).toBe(0);
  });

  test("a lost response is resent with the same operation id after a restart", async () => {
    const seen: Op[][] = [];
    installPush("network", seen);
    await createCustomerOffline(tenant, membership, { name: "Retry", phone: "+96170123456" });
    await flushOutbox(tenant, membership);
    const first = (await listOutbox(tenant, membership))[0]!;
    expect(first.state).toBe("retryable_failed");
    expect(first.attempts).toBe(1);
    forgetLocalDatabase(tenant, membership); // browser restart keeps IndexedDB
    installPush("applied", seen);
    await flushOutbox(tenant, membership);
    expect(seen).toHaveLength(2);
    expect(seen[1]?.[0]?.operation_id).toBe(seen[0]?.[0]?.operation_id);
    expect((await listOutbox(tenant, membership))[0]?.state).toBe("acknowledged");
  });

  test("a stale edit becomes a conflict that is never merged silently and can be resolved either way", async () => {
    const seen: Op[][] = [];
    installPush("applied", seen);
    const created = await createCustomerOffline(tenant, membership, { name: "Maya", phone: "+96170123456" });
    await flushOutbox(tenant, membership);
    await updateCustomerOffline(tenant, membership, created.id, { address: "Device St" });
    installPush("conflict", seen);
    const summary = await flushOutbox(tenant, membership);
    expect(summary.conflicts).toBe(1);
    const db = openLocalDatabase(tenant, membership);
    expect((await db.customers.get(created.id))?.address).toBe("Device St"); // local edit preserved
    const conflict = (await listOutbox(tenant, membership)).find((row) => row.state === "conflict")!;
    expect(conflict.expected_version).toBe(1);

    await acceptServerVersion(tenant, membership, conflict.seq!);
    expect((await db.customers.get(created.id))).toMatchObject({ address: "Server St", version: 5 });
    expect((await listOutbox(tenant, membership)).find((row) => row.seq === conflict.seq)?.state).toBe("rejected");

    // Alternative resolution: resend against the server version with a fresh command id.
    await updateCustomerOffline(tenant, membership, created.id, { address: "Device again" });
    installPush("conflict", seen);
    await flushOutbox(tenant, membership);
    const second = (await listOutbox(tenant, membership)).find((row) => row.state === "conflict")!;
    await retryWithServerVersion(tenant, membership, second.seq!);
    const retried = (await listOutbox(tenant, membership)).find((row) => row.seq === second.seq)!;
    expect(retried.state).toBe("pending");
    expect(retried.expected_version).toBe(5);
    expect(retried.operation_id).not.toBe(second.operation_id);
  });

  test("rejections are final and repeated outages end in a visible dead letter", async () => {
    const seen: Op[][] = [];
    installPush("reject", seen);
    await createCustomerOffline(tenant, membership, { name: "Bad", phone: "nope" });
    expect((await flushOutbox(tenant, membership)).rejected).toBe(1);
    expect((await listOutbox(tenant, membership))[0]).toMatchObject({ state: "rejected", last_error: "Customer phone is invalid" });

    installPush("server-error", seen);
    await createCustomerOffline(tenant, membership, { name: "Outage", phone: "+96170123457" });
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) await flushOutbox(tenant, membership);
    const dead = (await listOutbox(tenant, membership)).find((row) => row.payload.name === "Outage")!;
    expect(dead.state).toBe("dead_letter");
    expect(await retryDeadLetters(tenant, membership)).toBe(1);
    installPush("applied", seen);
    expect((await flushOutbox(tenant, membership)).acknowledged).toBe(1);
  });

  test("a protocol mismatch blocks sending but keeps every queued command intact", async () => {
    const seen: Op[][] = [];
    installPush("protocol-mismatch", seen);
    const created = await createCustomerOffline(tenant, membership, { name: "Kept Maya", phone: "+96170123456" });
    await updateCustomerOffline(tenant, membership, created.id, { address: "Kept St" });
    await expect(flushOutbox(tenant, membership)).rejects.toMatchObject({ code: "SYNC_PROTOCOL_MISMATCH" });
    const rows = await listOutbox(tenant, membership);
    expect(rows.map((row) => row.state)).toEqual(["pending", "pending"]);
    expect(rows.map((row) => row.attempts)).toEqual([0, 0]);
    expect(rows[0]?.last_error).toBe("update the app");
    // The same commands, same ids, go out once the app is updated.
    installPush("applied", seen);
    expect(await flushOutbox(tenant, membership)).toMatchObject({ sent: 2, acknowledged: 2 });
    expect(seen[1]?.map((op) => op.operation_id)).toEqual(rows.map((row) => row.operation_id));
  });
});
