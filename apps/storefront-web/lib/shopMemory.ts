/**
 * What the shop keeps on this device, only when useful to the visitor (D-102):
 * - contact details, only after the visitor ticks "Remember my details on this device";
 * - the provisional order's reference, for the server's 72-hour lifetime, so "Your order" reopens it;
 * and the pure helpers for the cart's calculated total and for ordering the same products again.
 * Nothing here is financial truth: the shop prices every line when it confirms the order.
 */
export const ORDER_LIFETIME_MS = 72 * 60 * 60 * 1000;

const CONTACT_KEY = (slug: string) => `tawzeevo.shop.${slug}.contact`;
const ORDER_KEY = (slug: string) => `tawzeevo.shop.${slug}.order`;
const ORDER_EVENT = "tawzeevo:order";

export interface RememberedContact { name: string; phone: string; address: string }

function storage(): Storage | null {
  try { return typeof localStorage === "undefined" ? null : localStorage; } catch { return null; }
}

export function readContact(slug: string): RememberedContact | null {
  try {
    const raw = storage()?.getItem(CONTACT_KEY(slug));
    const parsed = raw ? (JSON.parse(raw) as Partial<RememberedContact>) : null;
    if (!parsed || typeof parsed.name !== "string" || typeof parsed.phone !== "string" || typeof parsed.address !== "string") return null;
    return { name: parsed.name.slice(0, 200), phone: parsed.phone.slice(0, 64), address: parsed.address.slice(0, 500) };
  } catch {
    return null;
  }
}

export function rememberContact(slug: string, contact: RememberedContact): void {
  try { storage()?.setItem(CONTACT_KEY(slug), JSON.stringify({ name: contact.name.trim(), phone: contact.phone.trim(), address: contact.address.trim() })); } catch { /* private mode */ }
}

export function forgetContact(slug: string): void {
  try { storage()?.removeItem(CONTACT_KEY(slug)); } catch { /* ignore */ }
}

const REFERENCE = /^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/;

function announceOrder(): void {
  try { if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(ORDER_EVENT)); } catch { /* ignore */ }
}

/** Keeps the order reference with the order's creation time (ms), for its 72-hour lifetime. */
export function keepOrderReference(slug: string, reference: string, createdAt: number): void {
  if (!REFERENCE.test(reference) || !Number.isFinite(createdAt)) return;
  try { storage()?.setItem(ORDER_KEY(slug), JSON.stringify({ reference, created_at: createdAt })); } catch { /* private mode */ }
  announceOrder();
}

/** The kept reference while its order can still be opened; an expired or broken one is removed. */
export function readOrderReference(slug: string, now: number): string | null {
  try {
    const raw = storage()?.getItem(ORDER_KEY(slug));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { reference?: unknown; created_at?: unknown };
    const valid = typeof parsed.reference === "string" && REFERENCE.test(parsed.reference) && typeof parsed.created_at === "number" && now - parsed.created_at < ORDER_LIFETIME_MS && parsed.created_at <= now + 60_000;
    if (valid) return parsed.reference as string;
    storage()?.removeItem(ORDER_KEY(slug));
    return null;
  } catch {
    return null;
  }
}

export function forgetOrderReference(slug: string): void {
  try { storage()?.removeItem(ORDER_KEY(slug)); } catch { /* ignore */ }
  announceOrder();
}

export function onOrderChange(handler: () => void): () => void {
  window.addEventListener(ORDER_EVENT, handler);
  window.addEventListener("storage", handler);
  return () => { window.removeEventListener(ORDER_EVENT, handler); window.removeEventListener("storage", handler); };
}

// ---------- calculated total: exact decimal arithmetic on the server's 4-decimal strings ----------

const SCALE = 10000n;

function toUnits(value: string): bigint | null {
  const match = /^(-?)(\d+)(?:\.(\d{1,4}))?$/.exec(value.trim());
  if (!match) return null;
  const units = BigInt(match[2]!) * SCALE + BigInt(((match[3] ?? "") + "0000").slice(0, 4));
  return match[1] ? -units : units;
}

function fromUnits(units: bigint): string {
  const negative = units < 0n;
  const absolute = negative ? -units : units;
  return `${negative ? "-" : ""}${absolute / SCALE}.${(absolute % SCALE).toString().padStart(4, "0")}`;
}

/** The prices the catalog shows this visitor for one product (personalized when their link is). */
export interface ShownPrice { currency: string; piece_price: string; box_price: string | null }
export interface CartPriceLine { product_id: string; price_basis: "PIECE" | "BOX"; quantity: number }
export interface PricedLine { product_id: string; price_basis: "PIECE" | "BOX"; currency: string | null; unit_price: string | null; line_total: string | null }

/**
 * Lines and totals from the prices already shown to this visitor. Totals are per currency and
 * currencies are never added together (D-066). A line whose price is not available (the product is
 * no longer published, or it has no box price) is left out of every total and counted as missing.
 */
export function cartTotals(lines: CartPriceLine[], prices: Record<string, ShownPrice>): { lines: PricedLine[]; totals: { currency: string; total: string }[]; missing: number } {
  const sums = new Map<string, bigint>();
  let missing = 0;
  const priced = lines.map((line): PricedLine => {
    const shown = prices[line.product_id];
    const unit = shown ? toUnits((line.price_basis === "BOX" ? shown.box_price : shown.piece_price) ?? "") : null;
    if (!shown || unit === null || !Number.isInteger(line.quantity) || line.quantity <= 0) {
      missing += 1;
      return { product_id: line.product_id, price_basis: line.price_basis, currency: null, unit_price: null, line_total: null };
    }
    const total = unit * BigInt(line.quantity);
    sums.set(shown.currency, (sums.get(shown.currency) ?? 0n) + total);
    return { product_id: line.product_id, price_basis: line.price_basis, currency: shown.currency, unit_price: fromUnits(unit), line_total: fromUnits(total) };
  });
  const totals = [...sums.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([currency, total]) => ({ currency, total: fromUnits(total) }));
  return { lines: priced, totals, missing };
}

// ---------- order these again ----------

export interface OrderedItem { product_id?: string | null; name: string; quantity: string; unit: string }
export interface AvailableProduct { id: string; name: string; name_ar: string | null; box_price: string | null }
export interface ReorderLine { product_id: string; name: string; price_basis: "PIECE" | "BOX"; unit_label: string; quantity: number }

/**
 * The ordered products that can be ordered again, with their quantities (whole units, at least 1).
 * Lines typed by the shop, products no longer published, and boxes of a product no longer sold by
 * the box are skipped and counted.
 */
export function reorderLines(items: OrderedItem[], available: Record<string, AvailableProduct>, lang: "en" | "ar", labels: { piece: string; box: string }): { lines: ReorderLine[]; skipped: number } {
  const lines: ReorderLine[] = [];
  let skipped = 0;
  for (const item of items) {
    const product = item.product_id ? available[item.product_id] : undefined;
    const basis = item.unit === "BOX" ? "BOX" : "PIECE";
    const quantity = Math.max(1, Math.round(Number(item.quantity)));
    if (!product || (basis === "BOX" && !product.box_price) || !Number.isFinite(quantity)) { skipped += 1; continue; }
    lines.push({ product_id: product.id, name: lang === "ar" && product.name_ar ? product.name_ar : product.name, price_basis: basis, unit_label: basis === "BOX" ? labels.box : labels.piece, quantity: Math.min(100000, quantity) });
  }
  return { lines, skipped };
}
