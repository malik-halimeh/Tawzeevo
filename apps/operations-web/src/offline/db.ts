import Dexie, { type EntityTable } from "dexie";

/**
 * Local operational projection and outbox (PHASE_04.md E). One database per tenant membership so
 * two businesses on one device never share rows; the device installation id lives in localStorage
 * because it is a deduplication identity, never a credential. Access/refresh tokens are never
 * stored here.
 */
export const LOCAL_SCHEMA_VERSION = 2;
export const PROTOCOL_VERSION = 1;

export interface LocalCustomer {
  id: string;
  tenant_id: string;
  name: string;
  phone: string;
  phone_raw: string | null;
  address: string | null;
  latitude: string | null;
  longitude: string | null;
  grade: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface LocalCategory {
  id: string;
  tenant_id: string;
  master_category_id: string | null;
  name_en: string;
  name_ar: string;
  slug: string;
  display_order: number;
  is_active: boolean;
  archived_at: string | null;
  version: number;
}

export interface LocalProduct {
  id: string;
  tenant_id: string;
  category_id: string;
  master_product_id: string | null;
  name: string;
  is_published: boolean;
  unit_price: string;
  currency: string;
  price_basis: "PIECE" | "BOX";
  pieces_per_box: number | null;
  version: number;
}

export interface LocalBarcode {
  id: string;
  tenant_id: string;
  tenant_product_id: string;
  barcode: string;
  package_level: "PIECE" | "BOX";
}

export interface LocalInvoice {
  id: string;
  tenant_id: string;
  customer_id: string | null;
  status: "DRAFT" | "CONFIRMED" | "CANCELLED";
  official_invoice_number: string | null;
  current_revision_id: string;
  confirmed_revision_id: string | null;
  confirmed_at: string | null;
  cancelled_at: string | null;
  updated_at: string;
  /** Set while the header exists only on this device; never an official number. */
  pending_reference?: string | null;
}

export interface LocalRevision {
  id: string;
  tenant_id: string;
  invoice_id: string;
  server_revision_number: number;
  currency: string;
  customer_id: string | null;
  prior_balance_snapshot: string;
  subtotal: string;
  discount_total: string;
  markup_total: string;
  net_sales: string;
  amount_due_display: string;
  created_at: string;
}

export interface LocalRevisionItem {
  id: string;
  tenant_id: string;
  invoice_revision_id: string;
  line_number: number;
  tenant_product_id: string | null;
  product_name: string;
  barcode: string | null;
  quantity: string;
  price_basis: "PIECE" | "BOX";
  pieces_per_box: number | null;
  normal_unit_price: string;
  effective_unit_price: string;
  line_discount: string;
  line_markup: string;
  line_total: string;
}

export interface LocalPayment {
  id: string;
  tenant_id: string;
  customer_id: string | null;
  supplier_id: string | null;
  direction: string;
  currency: string;
  amount: string;
  paid_at: string;
  reverses_payment_id: string | null;
}

export interface LocalLedgerEntry {
  id: string;
  tenant_id: string;
  customer_id: string;
  currency: string;
  signed_amount: string;
  entry_type: string;
  source_type: string | null;
  source_id: string | null;
  effective_at: string;
}

export type OutboxState =
  | "pending"
  | "sending"
  | "acknowledged"
  | "retryable_failed"
  | "conflict"
  | "rejected"
  | "dead_letter";

export interface OutboxRecord {
  seq?: number;
  operation_id: string;
  tenant_id: string;
  membership_id: string;
  device_installation_id: string;
  entity_type: string;
  entity_id: string;
  operation_type: string;
  expected_version: number | null;
  payload: Record<string, unknown>;
  client_timestamp: string;
  protocol_version: number;
  state: OutboxState;
  attempts: number;
  last_error: string | null;
  result: Record<string, unknown> | null;
}

export interface LocalMedia {
  local_id: string;
  tenant_id: string;
  entity_type: string;
  entity_id: string;
  /** Raw bytes rather than a Blob: some WebViews fail to store Blobs in IndexedDB. */
  bytes: ArrayBuffer;
  checksum: string;
  content_type: string;
  byte_size: number;
  state: "queued" | "uploading" | "uploaded" | "failed";
  attempts: number;
  remote_id: string | null;
  last_error: string | null;
}

export interface MetaRecord {
  key: string;
  value: string;
}

export class TawzeevoLocalDatabase extends Dexie {
  customers!: EntityTable<LocalCustomer, "id">;
  categories!: EntityTable<LocalCategory, "id">;
  products!: EntityTable<LocalProduct, "id">;
  barcodes!: EntityTable<LocalBarcode, "id">;
  invoices!: EntityTable<LocalInvoice, "id">;
  revisions!: EntityTable<LocalRevision, "id">;
  revisionItems!: EntityTable<LocalRevisionItem, "id">;
  payments!: EntityTable<LocalPayment, "id">;
  ledgerEntries!: EntityTable<LocalLedgerEntry, "id">;
  outbox!: EntityTable<OutboxRecord, "seq">;
  media!: EntityTable<LocalMedia, "local_id">;
  meta!: EntityTable<MetaRecord, "key">;

  constructor(name: string) {
    super(name);
    // Every schema step stays here forever: a device may skip several app releases and must
    // upgrade through each version without losing queued work (PHASE_04.md N).
    this.version(1).stores({
      customers: "id, phone, name",
      categories: "id, slug",
      products: "id, category_id, name",
      barcodes: "id, barcode, tenant_product_id",
      invoices: "id, customer_id, status",
      revisions: "id, invoice_id",
      revisionItems: "id, invoice_revision_id",
      payments: "id, customer_id",
      ledgerEntries: "id, customer_id, currency",
      outbox: "++seq, operation_id, state",
      media: "local_id, state",
      meta: "key",
    });
    // v2: invoices carry an explicit pending_reference; media stores raw bytes instead of a Blob.
    this.version(2)
      .stores({ invoices: "id, customer_id, status, pending_reference" })
      .upgrade((transaction) =>
        Promise.all([
          transaction.table("invoices").toCollection().modify((row: LocalInvoice) => {
            row.pending_reference ??= null;
          }),
          transaction.table("media").toCollection().modify((row: LocalMedia & { blob?: unknown }) => {
            if (row.bytes === undefined) {
              // A Blob cannot be read inside the upgrade transaction; the item must be re-picked.
              delete row.blob;
              row.bytes = new ArrayBuffer(0);
              row.state = "failed";
              row.attempts = Number.MAX_SAFE_INTEGER;
              row.last_error = "re-pick this image after the update";
            }
          }),
        ]).then(() => undefined),
      );
  }
}

const databases = new Map<string, TawzeevoLocalDatabase>();

export function localDatabaseName(tenantId: string, membershipId: string): string {
  return `tawzeevo-${tenantId}-${membershipId}`;
}

export function openLocalDatabase(tenantId: string, membershipId: string): TawzeevoLocalDatabase {
  const name = localDatabaseName(tenantId, membershipId);
  let db = databases.get(name);
  if (!db) {
    db = new TawzeevoLocalDatabase(name);
    databases.set(name, db);
  }
  return db;
}

/** Drop the in-memory handle (e.g. tab closed) while keeping the stored data. */
export function forgetLocalDatabase(tenantId: string, membershipId: string): void {
  const name = localDatabaseName(tenantId, membershipId);
  databases.get(name)?.close();
  databases.delete(name);
}

/** Purge and forget a tenant's local projection (logout, revocation, suspension). */
export async function deleteLocalDatabase(tenantId: string, membershipId: string): Promise<void> {
  const name = localDatabaseName(tenantId, membershipId);
  const db = databases.get(name);
  if (db) {
    db.close();
    databases.delete(name);
  }
  await Dexie.delete(name);
}

const DEVICE_KEY = "tawzeevo.device_installation_id";

export function getDeviceInstallationId(): string {
  try {
    const existing = localStorage.getItem(DEVICE_KEY);
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem(DEVICE_KEY, created);
    return created;
  } catch {
    // Storage unavailable (private mode): a per-session id still deduplicates within the session.
    return crypto.randomUUID();
  }
}
