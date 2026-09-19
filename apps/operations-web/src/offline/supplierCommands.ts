import { PROTOCOL_VERSION, type OutboxRecord, getDeviceInstallationId, openLocalDatabase } from "./db";

/**
 * Phase 6 offline commands (PHASE_06.md I) on the Phase 4 outbox: a supplier price append, a
 * procurement line edit with its expected version, and an actual purchase as a financial command.
 * The server names the row after the operation id (price append) or uses it as the idempotency
 * key (purchase), so a retried command never applies twice. No local projection is kept: the
 * owner sees the queued command in the outbox and the server truth after the next sync.
 */
type Phase6Entity = "supplier" | "product_cost" | "procurement_item" | "supplier_purchase" | "supplier_payment";

function command(
  tenantId: string,
  membershipId: string,
  entityType: Phase6Entity,
  operationType: "create" | "update" | "receipt",
  entityId: string,
  expectedVersion: number | null,
  payload: Record<string, unknown>,
  operationId?: string,
): OutboxRecord {
  return {
    operation_id: operationId ?? crypto.randomUUID(),
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

export interface CostAppendInput { product_id: string; supplier_id: string; unit_cost: string; currency: string; cost_basis: "PIECE" | "BOX"; pieces_per_box: number | null; source_type: "MANUAL" | "QUOTE"; quantity_context: string | null; notes: string | null }

/** The entry id doubles as the operation id, so the server appends exactly one row. */
export async function queueCostAppend(tenantId: string, membershipId: string, input: CostAppendInput): Promise<string> {
  const db = openLocalDatabase(tenantId, membershipId);
  const entryId = crypto.randomUUID();
  await db.outbox.add(command(tenantId, membershipId, "product_cost", "create", entryId, null, { ...input }, entryId));
  return entryId;
}

export async function queueProcurementItemEdit(tenantId: string, membershipId: string, itemId: string, expectedVersion: number, patch: { target_quantity?: string; supplier_id?: string; clear_supplier?: boolean; notes?: string }): Promise<string> {
  const db = openLocalDatabase(tenantId, membershipId);
  const cmd = command(tenantId, membershipId, "procurement_item", "update", itemId, expectedVersion, { ...patch });
  await db.outbox.add(cmd);
  return cmd.operation_id;
}

export interface PurchaseInput { idempotency_key: string; supplier_id: string; currency: string; procurement_list_id: string | null; supplier_reference: string | null; items: { product_id: string; quantity: string; unit_cost: string; procurement_item_id: string | null }[] }

/** The purchase's own idempotency key is the operation id (D-044): one intent, one purchase. */
export async function queuePurchase(tenantId: string, membershipId: string, input: PurchaseInput): Promise<string> {
  const db = openLocalDatabase(tenantId, membershipId);
  const cmd = command(tenantId, membershipId, "supplier_purchase", "create", input.idempotency_key, null, { ...input }, input.idempotency_key);
  await db.outbox.add(cmd);
  return cmd.operation_id;
}
