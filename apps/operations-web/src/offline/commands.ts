import { PROTOCOL_VERSION, type LocalInvoice, type OutboxRecord, getDeviceInstallationId, openLocalDatabase } from "./db";

/**
 * Offline financial commands (PHASE_04.md D/I). The device queues the exact request the online
 * editor would send; the server reuses the Phase 3 services. Official invoice numbers and server
 * revision numbers are never fabricated here: a queued invoice shows a clearly pending local
 * reference until the acknowledged projection replaces it.
 */
export function pendingReference(invoiceId: string): string {
  return `PENDING-${invoiceId.slice(0, 8).toUpperCase()}`;
}

function command(
  tenantId: string,
  membershipId: string,
  entityType: "invoice" | "payment",
  operationType: "create" | "update" | "confirm" | "cancel" | "receipt" | "refund" | "reverse",
  entityId: string,
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
    expected_version: null,
    payload,
    client_timestamp: new Date().toISOString(),
    protocol_version: PROTOCOL_VERSION,
    state: "pending",
    attempts: 0,
    last_error: null,
    result: null,
  };
}

export interface DraftCommandInput {
  customer_id: string;
  currency: string;
  invoice_discount_expression: string;
  invoice_markup_expression: string;
  items: Record<string, unknown>[];
  expected_predecessor_revision_id?: string | null;
  confirmed?: boolean;
  /** D-045: reuse the create command id the online editor already sent, so a replay dedupes. */
  client_command_id?: string | null;
}

/** Queue a new draft; the invoice appears locally at once with a pending reference. */
export async function queueInvoiceDraft(tenantId: string, membershipId: string, input: DraftCommandInput): Promise<LocalInvoice> {
  const db = openLocalDatabase(tenantId, membershipId);
  const invoiceId = crypto.randomUUID();
  const now = new Date().toISOString();
  const local: LocalInvoice = {
    id: invoiceId,
    tenant_id: tenantId,
    customer_id: input.customer_id,
    status: "DRAFT",
    official_invoice_number: null,
    current_revision_id: "",
    confirmed_revision_id: null,
    confirmed_at: null,
    cancelled_at: null,
    updated_at: now,
    pending_reference: pendingReference(invoiceId),
  };
  const cmd = command(tenantId, membershipId, "invoice", "create", invoiceId, {
    customer_id: input.customer_id,
    currency: input.currency,
    invoice_discount_expression: input.invoice_discount_expression,
    invoice_markup_expression: input.invoice_markup_expression,
    items: input.items,
    ...(input.client_command_id ? { client_command_id: input.client_command_id } : {}),
  });
  await db.transaction("rw", [db.invoices, db.outbox], async () => {
    await db.invoices.put(local);
    await db.outbox.add(cmd);
  });
  return local;
}

/** Queue an edit of a known server invoice (draft or confirmed) with its predecessor revision. */
export async function queueInvoiceUpdate(tenantId: string, membershipId: string, invoiceId: string, input: DraftCommandInput): Promise<void> {
  const db = openLocalDatabase(tenantId, membershipId);
  const cmd = command(tenantId, membershipId, "invoice", "update", invoiceId, {
    customer_id: input.customer_id,
    currency: input.currency,
    invoice_discount_expression: input.invoice_discount_expression,
    invoice_markup_expression: input.invoice_markup_expression,
    items: input.items,
    expected_predecessor_revision_id: input.expected_predecessor_revision_id ?? null,
    confirmed: Boolean(input.confirmed),
  });
  await db.transaction("rw", [db.invoices, db.outbox], async () => {
    const current = await db.invoices.get(invoiceId);
    if (current) await db.invoices.put({ ...current, updated_at: new Date().toISOString(), pending_reference: current.pending_reference ?? pendingReference(invoiceId) });
    await db.outbox.add(cmd);
  });
}

export async function queueInvoiceConfirm(tenantId: string, membershipId: string, invoiceId: string, expectedRevisionId: string): Promise<void> {
  const db = openLocalDatabase(tenantId, membershipId);
  await db.transaction("rw", [db.invoices, db.outbox], async () => {
    const current = await db.invoices.get(invoiceId);
    if (current) await db.invoices.put({ ...current, pending_reference: current.pending_reference ?? pendingReference(invoiceId) });
    await db.outbox.add(command(tenantId, membershipId, "invoice", "confirm", invoiceId, { expected_revision_id: expectedRevisionId }));
  });
}

export async function queueInvoiceCancel(tenantId: string, membershipId: string, invoiceId: string, reason: string | null): Promise<void> {
  const db = openLocalDatabase(tenantId, membershipId);
  await db.outbox.add(command(tenantId, membershipId, "invoice", "cancel", invoiceId, { reason }));
}

export interface ReceiptCommandInput {
  customer_id: string;
  amount: string;
  currency: string;
  method?: string | null;
  reference?: string | null;
  paid_at: string;
  allocations?: Record<string, unknown>[] | null;
  /** D-044: the intent key already used online, so the server replays instead of double-charging. */
  idempotency_key?: string | null;
}

export async function queueReceipt(tenantId: string, membershipId: string, input: ReceiptCommandInput): Promise<string> {
  const db = openLocalDatabase(tenantId, membershipId);
  const cmd = command(tenantId, membershipId, "payment", "receipt", crypto.randomUUID(), {
    ...(input.idempotency_key ? { idempotency_key: input.idempotency_key } : {}),
    customer_id: input.customer_id,
    amount: input.amount,
    currency: input.currency,
    method: input.method ?? null,
    reference: input.reference ?? null,
    paid_at: input.paid_at,
    allocations: input.allocations ?? null,
  });
  await db.outbox.add(cmd);
  return cmd.operation_id;
}

export async function queueRefund(tenantId: string, membershipId: string, input: Omit<ReceiptCommandInput, "allocations">): Promise<string> {
  const db = openLocalDatabase(tenantId, membershipId);
  const cmd = command(tenantId, membershipId, "payment", "refund", crypto.randomUUID(), {
    ...(input.idempotency_key ? { idempotency_key: input.idempotency_key } : {}),
    customer_id: input.customer_id,
    amount: input.amount,
    currency: input.currency,
    method: input.method ?? null,
    reference: input.reference ?? null,
    paid_at: input.paid_at,
  });
  await db.outbox.add(cmd);
  return cmd.operation_id;
}

/** Invoices created on this device that the server has not acknowledged yet. */
export async function pendingInvoices(tenantId: string, membershipId: string): Promise<LocalInvoice[]> {
  const db = openLocalDatabase(tenantId, membershipId);
  return (await db.invoices.toArray()).filter((row) => row.pending_reference);
}
