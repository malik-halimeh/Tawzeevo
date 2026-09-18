"use client";

/**
 * Cart state lives only in this browser (localStorage, one cart per shop). It holds product ids,
 * names and quantities — never prices as truth: the server prices every line at checkout.
 */
export interface CartLine {
  product_id: string;
  name: string;
  quantity: number;
  price_basis: "PIECE" | "BOX";
  unit_label: string;
}

const KEY = (slug: string) => `tawzeevo.cart.${slug}`;
const EVENT = "tawzeevo:cart";

export function readCart(slug: string): CartLine[] {
  try {
    const raw = localStorage.getItem(KEY(slug));
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(parsed) ? (parsed as CartLine[]).filter((line) => line && typeof line.product_id === "string" && line.quantity > 0) : [];
  } catch {
    return [];
  }
}

function write(slug: string, lines: CartLine[]): void {
  try {
    localStorage.setItem(KEY(slug), JSON.stringify(lines));
  } catch {
    /* private mode: the cart simply does not persist */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { slug } }));
}

export function addToCart(slug: string, line: Omit<CartLine, "quantity">, quantity = 1): CartLine[] {
  const lines = readCart(slug);
  const existing = lines.find((row) => row.product_id === line.product_id && row.price_basis === line.price_basis);
  if (existing) existing.quantity = Math.min(100000, existing.quantity + quantity);
  else lines.push({ ...line, quantity });
  write(slug, lines);
  return lines;
}

export function setQuantity(slug: string, productId: string, basis: CartLine["price_basis"], quantity: number): CartLine[] {
  const lines = readCart(slug)
    .map((row) => (row.product_id === productId && row.price_basis === basis ? { ...row, quantity } : row))
    .filter((row) => row.quantity > 0);
  write(slug, lines);
  return lines;
}

export function clearCart(slug: string): void {
  write(slug, []);
}

export function cartCount(slug: string): number {
  return readCart(slug).reduce((sum, row) => sum + row.quantity, 0);
}

export function onCartChange(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  window.addEventListener("storage", handler);
  return () => { window.removeEventListener(EVENT, handler); window.removeEventListener("storage", handler); };
}

/** One idempotency key per cart attempt, kept until the order is accepted (D-046 retries). */
export function checkoutKey(slug: string): string {
  const key = `tawzeevo.checkout-key.${slug}`;
  try {
    const existing = sessionStorage.getItem(key);
    if (existing) return existing;
    const created = crypto.randomUUID();
    sessionStorage.setItem(key, created);
    return created;
  } catch {
    return crypto.randomUUID();
  }
}

export function resetCheckoutKey(slug: string): void {
  try { sessionStorage.removeItem(`tawzeevo.checkout-key.${slug}`); } catch { /* ignore */ }
}
