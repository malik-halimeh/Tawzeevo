import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { pendingInvoices, pendingReference, queueInvoiceConfirm, queueInvoiceDraft, queueReceipt } from "./commands";
import { deleteLocalDatabase, openLocalDatabase } from "./db";
import { flushOutbox, listOutbox } from "./outbox";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";
const customer = "33333333-3333-4333-8333-333333333333";

type Op = { operation_id: string; entity_type: string; operation_type: string; entity_id: string; payload: Record<string, unknown> };

/** Server double: the create returns a server-assigned header id; confirm assigns the official number. */
function installPush(seen: Op[][], serverInvoiceId: string) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    if (!url.includes("/api/v1/sync/push")) return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
    const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as { operations: Op[] };
    seen.push(body.operations);
    return Promise.resolve(Response.json({
      high_water_change_seq: 7,
      results: body.operations.map((op) => {
        const base = { operation_id: op.operation_id, replayed: false, entity_type: op.entity_type, version: null, error: null, conflict: null };
        if (op.entity_type === "invoice" && op.operation_type === "create") {
          return { ...base, status: "applied", entity_id: serverInvoiceId, projection: { id: serverInvoiceId, tenant_id: tenant, customer_id: customer, status: "DRAFT", official_invoice_number: null, current_revision_id: "rev-1", confirmed_at: null } };
        }
        if (op.entity_type === "invoice" && op.operation_type === "confirm") {
          return { ...base, status: "applied", entity_id: op.entity_id, projection: { id: op.entity_id, tenant_id: tenant, customer_id: customer, status: "CONFIRMED", official_invoice_number: "INV-2026-000001", current_revision_id: "rev-1", confirmed_at: "2026-09-18T08:00:00Z" } };
        }
        if (op.entity_type === "payment") {
          return { ...base, status: "applied", entity_id: op.entity_id, projection: { id: "44444444-4444-4444-8444-444444444444", tenant_id: tenant, customer_id: customer, direction: "CUSTOMER_RECEIPT", currency: "USD", amount: op.payload.amount, paid_at: op.payload.paid_at, reverses_payment_id: null } };
        }
        return { ...base, status: "rejected", entity_id: op.entity_id, projection: null, error: { code: "UNSUPPORTED_OPERATION", message: "unsupported" } };
      }),
    }));
  }));
}

describe("offline financial commands", () => {
  beforeEach(async () => { localStorage.clear(); await deleteLocalDatabase(tenant, membership); });
  afterEach(() => { vi.unstubAllGlobals(); });

  test("a queued draft shows a pending reference, never an official number, until the server acknowledges it", async () => {
    const seen: Op[][] = [];
    const serverId = "55555555-5555-4555-8555-555555555555";
    installPush(seen, serverId);
    const local = await queueInvoiceDraft(tenant, membership, {
      customer_id: customer,
      currency: "USD",
      invoice_discount_expression: "0",
      invoice_markup_expression: "0",
      items: [{ product_id: null, manual_name: "Ice", quantity: "1", unit_price: "3.0000" }],
      client_command_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    });
    expect(local.official_invoice_number).toBeNull();
    expect(local.pending_reference).toBe(pendingReference(local.id));
    expect((await pendingInvoices(tenant, membership)).map((row) => row.id)).toEqual([local.id]);
    expect((await listOutbox(tenant, membership)).map((row) => row.state)).toEqual(["pending"]);

    const summary = await flushOutbox(tenant, membership);
    expect(summary).toMatchObject({ sent: 1, acknowledged: 1, rejected: 0, conflicts: 0 });
    // The command carried the same D-045 create identity the online editor used.
    expect(seen[0]?.[0]?.payload.client_command_id).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
    const db = openLocalDatabase(tenant, membership);
    expect(await db.invoices.get(local.id)).toBeUndefined();
    expect(await db.invoices.get(serverId)).toMatchObject({ status: "DRAFT", official_invoice_number: null, pending_reference: null });
    expect(await pendingInvoices(tenant, membership)).toEqual([]);
  });

  test("confirm and receipt commands are queued in order and their projections replace local rows", async () => {
    const seen: Op[][] = [];
    const serverId = "55555555-5555-4555-8555-555555555555";
    installPush(seen, serverId);
    const db = openLocalDatabase(tenant, membership);
    await db.invoices.put({ id: serverId, tenant_id: tenant, customer_id: customer, status: "DRAFT", official_invoice_number: null, current_revision_id: "rev-1", confirmed_revision_id: null, confirmed_at: null, cancelled_at: null, updated_at: "" });

    await queueInvoiceConfirm(tenant, membership, serverId, "rev-1");
    expect((await db.invoices.get(serverId))?.pending_reference).toBe(pendingReference(serverId));
    const receiptOperation = await queueReceipt(tenant, membership, {
      customer_id: customer,
      amount: "10.0000",
      currency: "USD",
      paid_at: "2026-09-18T08:00:00Z",
      idempotency_key: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    });

    const summary = await flushOutbox(tenant, membership);
    expect(summary).toMatchObject({ sent: 2, acknowledged: 2 });
    expect(seen[0]?.map((op) => op.operation_type)).toEqual(["confirm", "receipt"]);
    expect(seen[0]?.[0]?.payload).toEqual({ expected_revision_id: "rev-1" });
    expect(seen[0]?.[1]?.operation_id).toBe(receiptOperation);
    expect(seen[0]?.[1]?.payload.idempotency_key).toBe("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb");
    expect(await db.invoices.get(serverId)).toMatchObject({ status: "CONFIRMED", official_invoice_number: "INV-2026-000001", confirmed_revision_id: "rev-1", pending_reference: null });
    expect(await db.payments.get("44444444-4444-4444-8444-444444444444")).toMatchObject({ direction: "CUSTOMER_RECEIPT", amount: "10.0000", customer_id: customer });
  });
});
