import type { Table } from "dexie";

import { apiRequest } from "../api/client";
import {
  LOCAL_SCHEMA_VERSION,
  PROTOCOL_VERSION,
  type LocalBarcode,
  type LocalCategory,
  type LocalCustomer,
  type LocalInvoice,
  type LocalLedgerEntry,
  type LocalPayment,
  type LocalProduct,
  type LocalRevision,
  type LocalRevisionItem,
  type TawzeevoLocalDatabase,
  getDeviceInstallationId,
  openLocalDatabase,
} from "./db";

interface BootstrapResponse {
  device: { id: string; device_installation_id: string; lease_expires_at: string; revoked_at: string | null };
  high_water_change_seq: number;
  protocol_version: number;
  app_schema_version: number;
  collections: string[];
  page_size: number;
}

interface SnapshotPage<T> {
  collection: string;
  items: T[];
  next_cursor: string | null;
  high_water_change_seq: number;
}

export interface BootstrapProgress {
  collection: string;
  downloaded: number;
}

export interface LocalSyncStatus {
  device_installation_id: string;
  bootstrapped_at: string | null;
  cursor: number;
  lease_expires_at: string | null;
  counts: { customers: number; products: number; invoices: number; outbox_pending: number };
}

type AnyTable = Table<Record<string, unknown>, string>;

const COLLECTION_STORE: Record<string, (db: TawzeevoLocalDatabase) => AnyTable> = {
  customers: (db) => db.customers as unknown as AnyTable,
  categories: (db) => db.categories as unknown as AnyTable,
  tenant_products: (db) => db.products as unknown as AnyTable,
  tenant_barcodes: (db) => db.barcodes as unknown as AnyTable,
  invoices: (db) => db.invoices as unknown as AnyTable,
  invoice_revisions: (db) => db.revisions as unknown as AnyTable,
  invoice_revision_items: (db) => db.revisionItems as unknown as AnyTable,
  payments: (db) => db.payments as unknown as AnyTable,
  customer_ledger_entries: (db) => db.ledgerEntries as unknown as AnyTable,
};

const metaKey = (name: string) => `sync.${name}`;

async function readMeta(db: TawzeevoLocalDatabase, name: string): Promise<string | null> {
  const row = await db.meta.get(metaKey(name));
  return row?.value ?? null;
}

async function writeMeta(db: TawzeevoLocalDatabase, name: string, value: string): Promise<void> {
  await db.meta.put({ key: metaKey(name), value });
}

/**
 * Authorized bootstrap (PHASE_04.md G): register the device, then download every collection page
 * by page. Each page is written together with its resume cursor in one IndexedDB transaction, so
 * an interrupted download continues from the last stored page instead of restarting.
 */
export async function bootstrapLocalProjection(
  tenantId: string,
  membershipId: string,
  onProgress?: (progress: BootstrapProgress) => void,
): Promise<LocalSyncStatus> {
  const db = openLocalDatabase(tenantId, membershipId);
  const deviceId = getDeviceInstallationId();
  const inProgress = await readMeta(db, "bootstrap.in_progress");
  const started = inProgress
    ? (JSON.parse(inProgress) as BootstrapResponse)
    : await apiRequest<BootstrapResponse>(`/api/v1/sync/bootstrap?tenant_id=${tenantId}`, {
        method: "POST",
        body: JSON.stringify({
          device_installation_id: deviceId,
          protocol_version: PROTOCOL_VERSION,
          app_schema_version: LOCAL_SCHEMA_VERSION,
        }),
      });
  if (!inProgress) {
    // A fresh bootstrap replaces the projection; outbox and media (device-owned work) are kept.
    await db.transaction("rw", [db.customers, db.categories, db.products, db.barcodes, db.invoices, db.revisions, db.revisionItems, db.payments, db.ledgerEntries, db.meta], async () => {
      await Promise.all([
        db.customers.clear(), db.categories.clear(), db.products.clear(), db.barcodes.clear(),
        db.invoices.clear(), db.revisions.clear(), db.revisionItems.clear(), db.payments.clear(), db.ledgerEntries.clear(),
      ]);
      await writeMeta(db, "bootstrap.in_progress", JSON.stringify(started));
      await writeMeta(db, "device_installation_id", deviceId);
    });
  }

  for (const collection of started.collections) {
    const resolve = COLLECTION_STORE[collection];
    if (!resolve) continue;
    const store = resolve(db);
    const doneKey = `bootstrap.done.${collection}`;
    if ((await readMeta(db, doneKey)) === "1") continue;
    let cursor = await readMeta(db, `bootstrap.cursor.${collection}`);
    let downloaded = 0;
    for (;;) {
      const query = new URLSearchParams({ tenant_id: tenantId, device_installation_id: deviceId, page_size: String(started.page_size) });
      if (cursor) query.set("cursor", cursor);
      const page = await apiRequest<SnapshotPage<Record<string, unknown>>>(`/api/v1/sync/bootstrap/${collection}?${query.toString()}`);
      await db.transaction("rw", [store, db.meta], async () => {
        await store.bulkPut(page.items);
        if (page.next_cursor) await writeMeta(db, `bootstrap.cursor.${collection}`, page.next_cursor);
        else await writeMeta(db, doneKey, "1");
      });
      downloaded += page.items.length;
      onProgress?.({ collection, downloaded });
      if (!page.next_cursor) break;
      cursor = page.next_cursor;
    }
  }

  await db.transaction("rw", db.meta, async () => {
    await writeMeta(db, "cursor", String(started.high_water_change_seq));
    await writeMeta(db, "bootstrapped_at", new Date().toISOString());
    await writeMeta(db, "lease_expires_at", started.device.lease_expires_at);
    await db.meta.delete(metaKey("bootstrap.in_progress"));
    const keys = await db.meta.toCollection().primaryKeys();
    await db.meta.bulkDelete(keys.filter((key) => String(key).startsWith("sync.bootstrap.")));
  });
  return localSyncStatus(tenantId, membershipId);
}

export async function localSyncStatus(tenantId: string, membershipId: string): Promise<LocalSyncStatus> {
  const db = openLocalDatabase(tenantId, membershipId);
  const [customers, products, invoices, outboxPending] = await Promise.all([
    db.customers.count(),
    db.products.count(),
    db.invoices.count(),
    db.outbox.where("state").anyOf(["pending", "sending", "retryable_failed"]).count(),
  ]);
  return {
    device_installation_id: getDeviceInstallationId(),
    bootstrapped_at: await readMeta(db, "bootstrapped_at"),
    cursor: Number((await readMeta(db, "cursor")) ?? "0"),
    lease_expires_at: await readMeta(db, "lease_expires_at"),
    counts: { customers, products, invoices, outbox_pending: outboxPending },
  };
}

function digits(value: string): string {
  return value.replace(/[^0-9]/g, "");
}

/** Phone search over the local projection: exact normalized match, then suffix/contains match. */
export async function searchLocalCustomers(tenantId: string, membershipId: string, phone: string): Promise<LocalCustomer[]> {
  const db = openLocalDatabase(tenantId, membershipId);
  const needle = digits(phone);
  if (!needle) return [];
  const all = await db.customers.toArray();
  const exact = all.filter((row) => digits(row.phone) === needle || digits(row.phone).endsWith(needle.replace(/^0/, "")));
  const rows = exact.length ? exact : all.filter((row) => digits(row.phone).includes(needle) || (row.phone_raw ? digits(row.phone_raw).includes(needle) : false));
  return rows.sort((a, b) => a.name.localeCompare(b.name));
}

export async function findLocalProductByBarcode(tenantId: string, membershipId: string, barcode: string): Promise<{ product: LocalProduct; barcode: LocalBarcode } | null> {
  const db = openLocalDatabase(tenantId, membershipId);
  const match = await db.barcodes.where("barcode").equals(barcode.trim()).first();
  if (!match) return null;
  const product = await db.products.get(match.tenant_product_id);
  return product ? { product, barcode: match } : null;
}

export async function localCustomerBalances(tenantId: string, membershipId: string, customerId: string): Promise<{ currency: string; balance: string }[]> {
  const db = openLocalDatabase(tenantId, membershipId);
  const rows = await db.ledgerEntries.where("customer_id").equals(customerId).toArray();
  const totals = new Map<string, number>();
  for (const row of rows) totals.set(row.currency, (totals.get(row.currency) ?? 0) + Number(row.signed_amount));
  return [...totals.entries()].sort().map(([currency, balance]) => ({ currency, balance: balance.toFixed(4) }));
}

export type { LocalCategory, LocalCustomer, LocalInvoice, LocalLedgerEntry, LocalPayment, LocalProduct, LocalRevision, LocalRevisionItem };
