import { expect, test } from "vitest";

import i18n from "../i18n";

/**
 * Every command the offline modules can queue (offline/outbox.ts, offline/commands.ts,
 * offline/supplierCommands.ts) is listed in the Offline section's outbox by its entity and
 * operation; each must have a label in both languages, never a raw translation key.
 */
const ENTITIES = ["customer", "category", "tenant_product", "invoice", "payment", "supplier", "product_cost", "procurement_item", "supplier_purchase", "supplier_payment", "delivery_task"];
const OPERATIONS = ["create", "update", "archive", "confirm", "cancel", "receipt", "refund", "reverse", "complete"];

test.each(["en", "ar"])("every queued entity and operation has a %s label", (language) => {
  for (const entity of ENTITIES) expect(i18n.exists(`sync.entity.${entity}`, { lng: language })).toBe(true);
  for (const operation of OPERATIONS) expect(i18n.exists(`sync.operation.${operation}`, { lng: language })).toBe(true);
});
