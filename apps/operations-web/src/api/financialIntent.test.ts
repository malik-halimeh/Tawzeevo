import { afterEach, beforeEach, expect, test, vi } from "vitest";

const scope = "tenant:membership:customer:USD:CUSTOMER_RECEIPT";
const fields = {
  customer_id: "22222222-2222-2222-2222-222222222222",
  amount: "10.0000", currency: "USD", method: "CASH", reference: "first receipt",
  allocations: [{ target_ledger_entry_id: "77777777-7777-4777-8777-777777777777", amount: "10.0000" }],
};

beforeEach(() => { sessionStorage.clear(); });
afterEach(() => { vi.restoreAllMocks(); });

test("reload without module memory recovers the exact pending payload; only success permits a new identity", async () => {
  const firstModule = await import("./financialIntent");
  const first = firstModule.financialIntent(scope, fields);
  vi.resetModules();
  const reloaded = await import("./financialIntent");
  const recovered = reloaded.financialIntent(scope, { ...fields, amount: "99", reference: "edited", allocations: [] });
  expect(recovered).toEqual(first);
  expect(reloaded.financialIntent(scope, fields)).toEqual(first);
  reloaded.retireFinancialIntent(recovered);
  vi.resetModules();
  const nextModule = await import("./financialIntent");
  const next = nextModule.financialIntent(scope, fields);
  expect(next.payload.idempotency_key).not.toBe(first.payload.idempotency_key);
  // A late response from the old component cannot delete the new pending command.
  firstModule.retireFinancialIntent(first);
  expect(nextModule.financialIntent(scope, fields)).toEqual(next);
});

test("pending receipt/refund and membership/tenant/customer/currency scopes survive interleaving independently", async () => {
  const { financialIntent, retireFinancialIntent } = await import("./financialIntent");
  const scopes = [scope, ...[
    ["CUSTOMER_RECEIPT", "CUSTOMER_REFUND"], ["membership", "other-member"],
    ["tenant", "other-tenant"], ["customer", "other-customer"], ["USD", "LBP"],
  ].map(([from, to]) => scope.replace(from!, to!))];
  const pending = scopes.map((key) => financialIntent(key, fields));
  expect(new Set(pending.map((intent) => intent.payload.idempotency_key)).size).toBe(scopes.length);
  retireFinancialIntent(pending[1]!);
  scopes.filter((_, index) => index !== 1).forEach((key) => {
    expect(financialIntent(key, fields)).toEqual(pending[scopes.indexOf(key)]);
  });
});

test.each(["getItem", "setItem"] as const)("storage %s failure cannot create an unprotected command", async (method) => {
  const { financialIntent } = await import("./financialIntent");
  vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new Error("storage unavailable"); });
  expect(() => financialIntent(scope, fields)).toThrow();
});

test("unreadable or mismatched saved identity is never replaced by a fresh command", async () => {
  const { financialIntent } = await import("./financialIntent");
  const first = financialIntent(scope, fields);
  const key = sessionStorage.key(0)!;
  for (const value of ["{broken", JSON.stringify({ ...first, scope: "other" }), JSON.stringify({ ...first, payload: {} })]) {
    sessionStorage.setItem(key, value);
    expect(() => financialIntent(scope, fields)).toThrow();
    expect(sessionStorage.getItem(key)).toBe(value);
  }
});

test("failed retirement retains the original command for a safe replay", async () => {
  const { financialIntent, retireFinancialIntent } = await import("./financialIntent");
  const first = financialIntent(scope, fields);
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("storage unavailable"); });
  expect(() => retireFinancialIntent(first)).toThrow();
  expect(financialIntent(scope, fields)).toEqual(first);
});
