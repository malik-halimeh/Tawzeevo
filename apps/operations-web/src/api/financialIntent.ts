import { z } from "zod";

import { ApiError } from "./client";

const uuid = z.string().regex(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
const intentSchema = z.object({
  scope: z.string(),
  payload: z.object({
    idempotency_key: uuid,
    customer_id: uuid,
    amount: z.string(),
    currency: z.string(),
    method: z.string().nullable(),
    reference: z.string().nullable(),
    paid_at: z.string().datetime(),
    allocations: z.array(z.object({
      target_ledger_entry_id: uuid, amount: z.string(),
    }).strict()).nullable().optional(),
  }).strict(),
}).strict();

type PendingFinancialIntent = z.infer<typeof intentSchema>;
const storageKey = (scope: string) => `tawzeevo:online-financial-intent:v1:${scope}`;

function storageError(): ApiError {
  return new ApiError(0, "FINANCIAL_INTENT_STORAGE_UNAVAILABLE",
    "The pending payment could not be safely recovered or saved. Keep this tab open and retry when browser storage is available. Do not record the same payment in another tab.");
}

function readIntent(scope: string): PendingFinancialIntent | null {
  const saved = sessionStorage.getItem(storageKey(scope));
  if (saved === null) return null;
  const intent = intentSchema.parse(JSON.parse(saved));
  if (intent.scope !== scope) throw storageError();
  return intent;
}

// D-044: synchronous, same-tab reload recovery only. No background dispatch or offline outbox.
export function financialIntent(scope: string, fields: Record<string, unknown>): PendingFinancialIntent {
  try {
    const pending = readIntent(scope);
    if (pending) return pending;
    const command = intentSchema.parse({
      scope,
      payload: { ...fields, idempotency_key: crypto.randomUUID(), paid_at: new Date().toISOString() },
    });
    // Must succeed before the caller sends anything. Never fall back to memory-only submission.
    sessionStorage.setItem(storageKey(scope), JSON.stringify(command));
    return command;
  } catch {
    throw storageError();
  }
}

export function retireFinancialIntent(command: PendingFinancialIntent): void {
  try {
    // A late response from a destroyed component must not retire a later command.
    if (readIntent(command.scope)?.payload.idempotency_key === command.payload.idempotency_key) {
      sessionStorage.removeItem(storageKey(command.scope));
    }
  } catch {
    // Keeping an acknowledged command is safe: the next attempt replays it instead of duplicating it.
    throw storageError();
  }
}
