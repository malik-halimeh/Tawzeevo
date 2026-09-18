import type { Table } from "dexie";

import { ApiError, apiRequest } from "../api/client";
import { PROTOCOL_VERSION, type TawzeevoLocalDatabase, deleteLocalDatabase, getDeviceInstallationId, openLocalDatabase } from "./db";
import { type FlushSummary, flushOutbox } from "./outbox";
import { type LocalSyncStatus, bootstrapLocalProjection, localSyncStatus } from "./sync";

/**
 * Incremental pull (PHASE_04.md F/G/J): apply ordered change records to the local projection,
 * advance the cursor per page, re-bootstrap on 410, and purge/lock the local cache when the
 * server says this device or membership was revoked. Queued commands of a revoked device are
 * quarantined (marked rejected with the reason), never applied silently.
 */
interface ChangeRecord {
  change_seq: number;
  entity_type: string;
  entity_id: string;
  operation: "upsert" | "delete";
  version: number;
  payload: Record<string, unknown>;
}

interface PullResponse {
  changes: ChangeRecord[];
  next_cursor: number;
  high_water_change_seq: number;
  has_more: boolean;
  protocol_version: number;
}

export interface PullSummary {
  applied: number;
  pages: number;
  cursor: number;
  rebootstrapped: boolean;
}

export type SyncOutcome =
  | { kind: "ok"; push: FlushSummary; pull: PullSummary; status: LocalSyncStatus }
  | { kind: "revoked"; reason: string }
  | { kind: "offline" };

type AnyTable = Table<Record<string, unknown>, string>;

const ENTITY_STORE: Record<string, (db: TawzeevoLocalDatabase) => AnyTable> = {
  customer: (db) => db.customers as unknown as AnyTable,
  category: (db) => db.categories as unknown as AnyTable,
  tenant_product: (db) => db.products as unknown as AnyTable,
  tenant_barcode: (db) => db.barcodes as unknown as AnyTable,
  invoice: (db) => db.invoices as unknown as AnyTable,
  invoice_revision: (db) => db.revisions as unknown as AnyTable,
  invoice_revision_item: (db) => db.revisionItems as unknown as AnyTable,
  payment: (db) => db.payments as unknown as AnyTable,
  customer_ledger_entry: (db) => db.ledgerEntries as unknown as AnyTable,
};

async function readCursor(db: TawzeevoLocalDatabase): Promise<number> {
  return Number((await db.meta.get("sync.cursor"))?.value ?? "0");
}

export const REVOCATION_CODES = new Set([
  "SYNC_DEVICE_REVOKED",
  "TENANT_MEMBERSHIP_REQUIRED",
  "TENANT_MEMBERSHIP_INACTIVE",
  "TENANT_NOT_ACTIVE",
  "TENANT_SUSPENDED",
  "TENANT_OWNER_REQUIRED",
]);

export function isRevocation(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 403 && REVOCATION_CODES.has(error.code);
}

/** Lock this device out: quarantine pending commands, then drop the local projection. */
export async function quarantineAndPurge(tenantId: string, membershipId: string, reason: string): Promise<void> {
  const db = openLocalDatabase(tenantId, membershipId);
  const pending = await db.outbox.where("state").anyOf(["pending", "sending", "retryable_failed", "conflict"]).toArray();
  await db.outbox.bulkPut(pending.map((row) => ({ ...row, state: "rejected" as const, last_error: `quarantined: ${reason}` })));
  const quarantined = await db.outbox.toArray();
  try {
    localStorage.setItem(`tawzeevo.quarantine.${tenantId}.${membershipId}`, JSON.stringify(quarantined.map((row) => ({ operation_id: row.operation_id, entity_type: row.entity_type, operation_type: row.operation_type, reason }))));
  } catch {
    // Storage unavailable: the purge still proceeds; nothing revoked may remain usable.
  }
  await deleteLocalDatabase(tenantId, membershipId);
}

export async function pullChanges(tenantId: string, membershipId: string): Promise<PullSummary> {
  const db = openLocalDatabase(tenantId, membershipId);
  const deviceId = getDeviceInstallationId();
  let cursor = await readCursor(db);
  const summary: PullSummary = { applied: 0, pages: 0, cursor, rebootstrapped: false };
  for (;;) {
    const query = new URLSearchParams({ tenant_id: tenantId, device_installation_id: deviceId, cursor: String(cursor) });
    let page: PullResponse;
    try {
      page = await apiRequest<PullResponse>(`/api/v1/sync/pull?${query.toString()}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 410) {
        // Older than the retained history: re-download the snapshot; the outbox is preserved.
        const status = await bootstrapLocalProjection(tenantId, membershipId);
        return { applied: summary.applied, pages: summary.pages, cursor: status.cursor, rebootstrapped: true };
      }
      throw error;
    }
    if (page.protocol_version !== PROTOCOL_VERSION) throw new ApiError(409, "SYNC_PROTOCOL_MISMATCH", "Sync protocol changed; update the app");
    const tables = [...new Set(page.changes.map((change) => ENTITY_STORE[change.entity_type]).filter(Boolean))].map((resolve) => resolve!(db));
    await db.transaction("rw", [...tables, db.meta], async () => {
      for (const change of page.changes) {
        const resolve = ENTITY_STORE[change.entity_type];
        if (!resolve) continue;
        const store = resolve(db);
        if (change.operation === "delete") await store.delete(change.entity_id);
        else await store.put(change.payload);
      }
      await db.meta.put({ key: "sync.cursor", value: String(page.next_cursor) });
    });
    summary.applied += page.changes.length;
    summary.pages += 1;
    cursor = page.next_cursor;
    summary.cursor = cursor;
    if (!page.has_more) return summary;
  }
}

/** Push first so the pull reflects this device's own acknowledged work, then pull. */
export async function syncNow(tenantId: string, membershipId: string): Promise<SyncOutcome> {
  try {
    const push = await flushOutbox(tenantId, membershipId);
    const pull = await pullChanges(tenantId, membershipId);
    return { kind: "ok", push, pull, status: await localSyncStatus(tenantId, membershipId) };
  } catch (error) {
    if (isRevocation(error)) {
      await quarantineAndPurge(tenantId, membershipId, error.code);
      return { kind: "revoked", reason: error.code };
    }
    if (error instanceof TypeError) return { kind: "offline" };
    throw error;
  }
}
