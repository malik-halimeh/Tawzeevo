/**
 * Choices remembered on this device per business, so a form starts where the owner left off: the
 * category and currency of the last product, the currency of the last invoice. A convenience only;
 * nothing depends on it and a blocked storage simply remembers nothing.
 */
type Choice = "category" | "currency";
const key = (kind: Choice, tenantId: string) => `tawzeevo.last.${kind}.${tenantId}`;

export function readLastChoice(kind: Choice, tenantId: string): string | null {
  try { return localStorage.getItem(key(kind, tenantId)); } catch { return null; }
}

export function rememberChoice(kind: Choice, tenantId: string, value: string): void {
  try { localStorage.setItem(key(kind, tenantId), value); } catch { /* storage unavailable: nothing remembered */ }
}
