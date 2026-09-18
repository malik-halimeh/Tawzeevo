import { ApiError, apiRequest } from "../api/client";
import {
  PROTOCOL_VERSION,
  type LocalCategory,
  type LocalCustomer,
  type LocalProduct,
  type OutboxRecord,
  type OutboxState,
  getDeviceInstallationId,
  openLocalDatabase,
} from "./db";

/**
 * Device outbox (PHASE_04.md E/F/H). A local mutation and its outbox record are written in ONE
 * IndexedDB transaction, so a crash can never leave a local change without its command or a
 * command without its local change. The dispatcher sends pending commands in sequence order with
 * their original operation ids, so a lost response is simply resent and the server replays it.
 */
export const MAX_ATTEMPTS = 8;
export const PUSH_BATCH_SIZE = 50;

interface PushResult {
  operation_id: string;
  status: "applied" | "rejected" | "conflict";
  replayed: boolean;
  entity_type: string;
  entity_id: string;
  version: number | null;
  projection: Record<string, unknown> | null;
  error: { code: string; message: string } | null;
  conflict: {
    entity_type: string;
    entity_id: string;
    server_version: number;
    client_expected_version: number | null;
    server_projection: Record<string, unknown> | null;
    request_id: string;
  } | null;
}

interface PushResponse {
  results: PushResult[];
  high_water_change_seq: number;
}

export interface FlushSummary {
  sent: number;
  acknowledged: number;
  conflicts: number;
  rejected: number;
  failed: number;
  high_water_change_seq: number | null;
}

type EntityType = "customer" | "category" | "tenant_product";
type OperationType = "create" | "update" | "archive";

function newCommand(
  tenantId: string,
  membershipId: string,
  entityType: EntityType,
  operationType: OperationType,
  entityId: string,
  expectedVersion: number | null,
  payload: Record<string, unknown>,
): OutboxRecord {
  return {
    operation_id: crypto.randomUUID(),
    tenant_id: tenantId,
    membership_id: membershipId,
    device_installation_id: getDeviceInstallationId(),
    entity_type: entityType,
    entity_id: entityId,
    operation_type: operationType,
    expected_version: expectedVersion,
    payload,
    client_timestamp: new Date().toISOString(),
    protocol_version: PROTOCOL_VERSION,
    state: "pending",
    attempts: 0,
    last_error: null,
    result: null,
  };
}

/** Create a customer locally and queue the command in the same transaction. */
export async function createCustomerOffline(
  tenantId: string,
  membershipId: string,
  input: { name: string; phone: string; address?: string | null; grade?: string | null },
): Promise<LocalCustomer> {
  const db = openLocalDatabase(tenantId, membershipId);
  const now = new Date().toISOString();
  const row: LocalCustomer = {
    id: crypto.randomUUID(),
    tenant_id: tenantId,
    name: input.name,
    phone: input.phone,
    phone_raw: input.phone,
    address: input.address ?? null,
    latitude: null,
    longitude: null,
    grade: input.grade ?? null,
    version: 1,
    created_at: now,
    updated_at: now,
  };
  await db.transaction("rw", [db.customers, db.outbox], async () => {
    await db.customers.put(row);
    await db.outbox.add(newCommand(tenantId, membershipId, "customer", "create", row.id, null, {
      name: input.name, phone: input.phone, address: input.address ?? null, grade: input.grade ?? null,
    }));
  });
  return row;
}

/** Edit a customer locally with the version the device last saw; the server decides conflicts. */
export async function updateCustomerOffline(
  tenantId: string,
  membershipId: string,
  customerId: string,
  changes: Partial<Pick<LocalCustomer, "name" | "phone" | "address" | "grade">>,
): Promise<LocalCustomer> {
  const db = openLocalDatabase(tenantId, membershipId);
  return db.transaction("rw", [db.customers, db.outbox], async () => {
    const current = await db.customers.get(customerId);
    if (!current) throw new Error("CUSTOMER_NOT_LOCAL");
    const updated: LocalCustomer = { ...current, ...changes, updated_at: new Date().toISOString() };
    await db.customers.put(updated);
    await db.outbox.add(newCommand(tenantId, membershipId, "customer", "update", customerId, current.version, { ...changes }));
    return updated;
  });
}

export async function updateProductOffline(
  tenantId: string,
  membershipId: string,
  productId: string,
  changes: Partial<Pick<LocalProduct, "name" | "is_published" | "unit_price" | "pieces_per_box">>,
): Promise<LocalProduct> {
  const db = openLocalDatabase(tenantId, membershipId);
  return db.transaction("rw", [db.products, db.outbox], async () => {
    const current = await db.products.get(productId);
    if (!current) throw new Error("PRODUCT_NOT_LOCAL");
    const updated: LocalProduct = { ...current, ...changes };
    await db.products.put(updated);
    await db.outbox.add(newCommand(tenantId, membershipId, "tenant_product", "update", productId, current.version, { ...changes }));
    return updated;
  });
}

export async function archiveCategoryOffline(tenantId: string, membershipId: string, categoryId: string): Promise<LocalCategory> {
  const db = openLocalDatabase(tenantId, membershipId);
  return db.transaction("rw", [db.categories, db.outbox], async () => {
    const current = await db.categories.get(categoryId);
    if (!current) throw new Error("CATEGORY_NOT_LOCAL");
    const updated: LocalCategory = { ...current, is_active: false, archived_at: new Date().toISOString() };
    await db.categories.put(updated);
    await db.outbox.add(newCommand(tenantId, membershipId, "category", "archive", categoryId, current.version, {}));
    return updated;
  });
}

const STORE_FOR: Record<string, "customers" | "categories" | "products"> = {
  customer: "customers",
  category: "categories",
  tenant_product: "products",
};

async function applyResult(tenantId: string, membershipId: string, record: OutboxRecord, result: PushResult): Promise<OutboxState> {
  const db = openLocalDatabase(tenantId, membershipId);
  const storeName = STORE_FOR[record.entity_type];
  const store = storeName ? (db[storeName] as unknown as { put: (row: Record<string, unknown>) => Promise<unknown> }) : null;
  if (result.status === "applied") {
    if (store && result.projection) await store.put(result.projection);
    return "acknowledged";
  }
  if (result.status === "conflict") {
    // Never overwrite silently: keep the local edit visible next to the server version for manual merge.
    return "conflict";
  }
  return "rejected";
}

function isNetworkFailure(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof ApiError && error.status >= 500);
}

/** Send every pending command in order. Safe to call repeatedly; resends keep their ids. */
export async function flushOutbox(tenantId: string, membershipId: string): Promise<FlushSummary> {
  const db = openLocalDatabase(tenantId, membershipId);
  const summary: FlushSummary = { sent: 0, acknowledged: 0, conflicts: 0, rejected: 0, failed: 0, high_water_change_seq: null };
  const pending = (await db.outbox.where("state").anyOf(["pending", "retryable_failed"]).sortBy("seq")).slice(0, PUSH_BATCH_SIZE);
  if (!pending.length) return summary;
  await db.outbox.bulkPut(pending.map((row) => ({ ...row, state: "sending", attempts: row.attempts + 1 })));
  summary.sent = pending.length;
  let response: PushResponse;
  try {
    response = await apiRequest<PushResponse>(`/api/v1/sync/push?tenant_id=${tenantId}`, {
      method: "POST",
      body: JSON.stringify({
        device_installation_id: getDeviceInstallationId(),
        protocol_version: PROTOCOL_VERSION,
        operations: pending.map((row) => ({
          operation_id: row.operation_id,
          entity_type: row.entity_type,
          operation_type: row.operation_type,
          entity_id: row.entity_id,
          expected_version: row.expected_version,
          payload: row.payload,
          client_timestamp: row.client_timestamp,
        })),
      }),
    });
  } catch (error) {
    const retryable = isNetworkFailure(error);
    const message = error instanceof Error ? error.message : String(error);
    await db.outbox.bulkPut(pending.map((row) => ({
      ...row,
      attempts: row.attempts + 1,
      last_error: message,
      state: (retryable && row.attempts + 1 < MAX_ATTEMPTS ? "retryable_failed" : retryable ? "dead_letter" : "rejected"),
    })));
    summary.failed = pending.length;
    if (!retryable) throw error;
    return summary;
  }
  summary.high_water_change_seq = response.high_water_change_seq;
  const byId = new Map(response.results.map((result) => [result.operation_id, result]));
  for (const row of pending) {
    const result = byId.get(row.operation_id);
    if (!result) {
      await db.outbox.put({ ...row, attempts: row.attempts + 1, state: "retryable_failed", last_error: "missing result" });
      summary.failed += 1;
      continue;
    }
    const state = await applyResult(tenantId, membershipId, row, result);
    await db.outbox.put({ ...row, attempts: row.attempts + 1, state, result: result as unknown as Record<string, unknown>, last_error: result.error?.message ?? null });
    if (state === "acknowledged") summary.acknowledged += 1;
    else if (state === "conflict") summary.conflicts += 1;
    else summary.rejected += 1;
  }
  return summary;
}

export async function listOutbox(tenantId: string, membershipId: string): Promise<OutboxRecord[]> {
  return openLocalDatabase(tenantId, membershipId).outbox.orderBy("seq").toArray();
}

/** Owner resolved a conflict manually: take the server version locally and drop the command. */
export async function acceptServerVersion(tenantId: string, membershipId: string, seq: number): Promise<void> {
  const db = openLocalDatabase(tenantId, membershipId);
  await db.transaction("rw", [db.outbox, db.customers, db.categories, db.products], async () => {
    const row = await db.outbox.get(seq);
    if (!row || row.state !== "conflict") return;
    const projection = (row.result as { conflict?: { server_projection?: Record<string, unknown> } } | null)?.conflict?.server_projection;
    const storeName = STORE_FOR[row.entity_type];
    if (projection && storeName) await (db[storeName] as unknown as { put: (r: Record<string, unknown>) => Promise<unknown> }).put(projection);
    await db.outbox.put({ ...row, state: "rejected", last_error: "resolved: server version kept" });
  });
}

/** Owner resolved a conflict manually: resend the local edit against the current server version. */
export async function retryWithServerVersion(tenantId: string, membershipId: string, seq: number): Promise<void> {
  const db = openLocalDatabase(tenantId, membershipId);
  const row = await db.outbox.get(seq);
  if (!row || row.state !== "conflict") return;
  const serverVersion = (row.result as { conflict?: { server_version?: number } } | null)?.conflict?.server_version ?? null;
  await db.outbox.put({ ...row, operation_id: crypto.randomUUID(), expected_version: serverVersion, state: "pending", attempts: 0, result: null, last_error: null });
}

export async function retryDeadLetters(tenantId: string, membershipId: string): Promise<number> {
  const db = openLocalDatabase(tenantId, membershipId);
  const rows = await db.outbox.where("state").equals("dead_letter").toArray();
  await db.outbox.bulkPut(rows.map((row) => ({ ...row, state: "pending", attempts: 0 })));
  return rows.length;
}
