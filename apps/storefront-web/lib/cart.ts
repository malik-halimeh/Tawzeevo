"use client";

import { isContextRef } from "./format";

/**
 * Cart state lives only in this browser (localStorage, one cart per shop and personalized context).
 * It holds product ids, names and quantities — never prices as truth: the server prices every line
 * at checkout. Every function takes a cart id from `cartId`, so two customers' tabs never share one.
 */
export interface CartLine {
  product_id: string;
  name: string;
  quantity: number;
  price_basis: "PIECE" | "BOX";
  unit_label: string;
}

const KEY = (cart: string) => `tawzeevo.cart.${cart}`;
const EVENT = "tawzeevo:cart";

/** The public cart keeps its historical key; a personalized tab gets its own (D-090). */
export function cartId(slug: string, ctx?: string | null): string {
  return isContextRef(ctx) ? `${slug}.${ctx}` : slug;
}

export function readCart(cart: string): CartLine[] {
  try {
    const raw = localStorage.getItem(KEY(cart));
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    return Array.isArray(parsed) ? (parsed as CartLine[]).filter((line) => line && typeof line.product_id === "string" && line.quantity > 0) : [];
  } catch {
    return [];
  }
}

function write(cart: string, lines: CartLine[]): void {
  try {
    localStorage.setItem(KEY(cart), JSON.stringify(lines));
  } catch {
    /* private mode: the cart simply does not persist */
  }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { cart } }));
}

export function addToCart(cart: string, line: Omit<CartLine, "quantity">, quantity = 1): CartLine[] {
  const lines = readCart(cart);
  const existing = lines.find((row) => row.product_id === line.product_id && row.price_basis === line.price_basis);
  if (existing) existing.quantity = Math.min(100000, existing.quantity + quantity);
  else lines.push({ ...line, quantity });
  write(cart, lines);
  return lines;
}

export function setQuantity(cart: string, productId: string, basis: CartLine["price_basis"], quantity: number): CartLine[] {
  const lines = readCart(cart)
    .map((row) => (row.product_id === productId && row.price_basis === basis ? { ...row, quantity } : row))
    .filter((row) => row.quantity > 0);
  write(cart, lines);
  return lines;
}

export function clearCart(cart: string): void {
  write(cart, []);
}

export function cartCount(cart: string): number {
  return readCart(cart).reduce((sum, row) => sum + row.quantity, 0);
}

export function onCartChange(handler: () => void): () => void {
  window.addEventListener(EVENT, handler);
  window.addEventListener("storage", handler);
  return () => { window.removeEventListener(EVENT, handler); window.removeEventListener("storage", handler); };
}

/** One idempotency key per cart attempt, kept until the order is accepted (D-046 retries). */
export function checkoutKey(cart: string): string {
  const key = `tawzeevo.checkout-key.${cart}`;
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

export function resetCheckoutKey(cart: string): void {
  try { sessionStorage.removeItem(`tawzeevo.checkout-key.${cart}`); } catch { /* ignore */ }
}
