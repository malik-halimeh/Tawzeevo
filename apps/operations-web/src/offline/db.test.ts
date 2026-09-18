import "fake-indexeddb/auto";

import Dexie from "dexie";
import { afterEach, beforeEach, describe, expect, test } from "vitest";

import { LOCAL_SCHEMA_VERSION, deleteLocalDatabase, forgetLocalDatabase, localDatabaseName, openLocalDatabase } from "./db";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";

describe("local database schema", () => {
  beforeEach(async () => { await deleteLocalDatabase(tenant, membership); });
  afterEach(() => { forgetLocalDatabase(tenant, membership); });

  test("a device on the first schema upgrades in place and keeps its queued work", async () => {
    // Write with the historical v1 definition, exactly as an older app release left it.
    const legacy = new Dexie(localDatabaseName(tenant, membership));
    legacy.version(1).stores({
      customers: "id, phone, name", categories: "id, slug", products: "id, category_id, name", barcodes: "id, barcode, tenant_product_id",
      invoices: "id, customer_id, status", revisions: "id, invoice_id", revisionItems: "id, invoice_revision_id", payments: "id, customer_id",
      ledgerEntries: "id, customer_id, currency", outbox: "++seq, operation_id, state", media: "local_id, state", meta: "key",
    });
    await legacy.table("invoices").put({ id: "inv-1", tenant_id: tenant, customer_id: "c1", status: "DRAFT", official_invoice_number: null, current_revision_id: "r1", confirmed_revision_id: null, confirmed_at: null, cancelled_at: null, updated_at: "" });
    await legacy.table("outbox").add({ operation_id: "op-1", tenant_id: tenant, membership_id: membership, device_installation_id: "d", entity_type: "customer", entity_id: "c2", operation_type: "create", expected_version: null, payload: { name: "Queued" }, client_timestamp: "", protocol_version: 1, state: "pending", attempts: 0, last_error: null, result: null });
    await legacy.table("media").put({ local_id: "m-1", tenant_id: tenant, entity_type: "tenant_product", entity_id: "p1", blob: new Blob(["x"]), checksum: "c", content_type: "image/png", byte_size: 1, state: "queued", attempts: 0, remote_id: null, last_error: null });
    await legacy.table("meta").put({ key: "sync.cursor", value: 42 });
    legacy.close();

    const db = openLocalDatabase(tenant, membership);
    await db.open();
    expect(db.verno).toBe(LOCAL_SCHEMA_VERSION);
    expect(await db.invoices.get("inv-1")).toMatchObject({ status: "DRAFT", pending_reference: null });
    expect((await db.outbox.toArray()).map((row) => [row.operation_id, row.state])).toEqual([["op-1", "pending"]]);
    expect(await db.meta.get("sync.cursor")).toMatchObject({ value: 42 });
    const media = await db.media.get("m-1");
    expect(media).toMatchObject({ state: "failed", last_error: "re-pick this image after the update" });
    expect((media as unknown as { blob?: unknown }).blob).toBeUndefined();
    expect(media?.bytes.byteLength).toBe(0);
  });

  test("closing and reopening the same database keeps the rows (restart persistence)", async () => {
    const db = openLocalDatabase(tenant, membership);
    await db.customers.put({ id: "c1", tenant_id: tenant, name: "Maya", phone: "+96170123456", phone_raw: null, address: null, latitude: null, longitude: null, grade: null, version: 1, created_at: "", updated_at: "" });
    forgetLocalDatabase(tenant, membership);
    const reopened = openLocalDatabase(tenant, membership);
    expect(reopened).not.toBe(db);
    expect(await reopened.customers.get("c1")).toMatchObject({ name: "Maya" });
  });
});
