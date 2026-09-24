import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { addToCart, cartCount, cartId, checkoutKey, readCart } from "./cart";
import { shopHref } from "./format";

/** In-memory Storage, so the cart runs in the node test environment exactly as in a browser tab. */
function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() { return data.size; },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => { data.delete(key); },
    setItem: (key, value) => { data.set(key, String(value)); },
  };
}

const A = "a".repeat(24);
const B = "b".repeat(24);
const water = { product_id: "p-water", name: "Water", price_basis: "PIECE" as const, unit_label: "piece" };
const rice = { product_id: "p-rice", name: "Rice", price_basis: "PIECE" as const, unit_label: "piece" };

describe("cart per personalized context (D-090)", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    vi.stubGlobal("sessionStorage", memoryStorage());
    vi.stubGlobal("window", { dispatchEvent: () => true });
    vi.stubGlobal("CustomEvent", class { constructor(public type: string) {} });
  });
  afterEach(() => { vi.unstubAllGlobals(); });

  test("two customers in one browser keep separate carts, and the public cart is a third", () => {
    // Customer A's tab adds water; customer B's tab adds rice; returning to A still shows only A's cart.
    addToCart(cartId("cedar", A), water, 2);
    addToCart(cartId("cedar", B), rice, 1);
    expect(readCart(cartId("cedar", A)).map((line) => [line.product_id, line.quantity])).toEqual([["p-water", 2]]);
    expect(readCart(cartId("cedar", B)).map((line) => [line.product_id, line.quantity])).toEqual([["p-rice", 1]]);
    expect(cartCount(cartId("cedar"))).toBe(0);
    addToCart(cartId("cedar"), water, 5);
    expect(cartCount(cartId("cedar", A))).toBe(2);
    expect(cartCount(cartId("cedar", B))).toBe(1);
    // Each context also has its own checkout attempt key.
    expect(checkoutKey(cartId("cedar", A))).not.toBe(checkoutKey(cartId("cedar", B)));
  });

  test("the public cart keeps its historical key and a malformed reference never scopes a cart", () => {
    expect(cartId("cedar")).toBe("cedar");
    expect(cartId("cedar", null)).toBe("cedar");
    expect(cartId("cedar", "not-a-ref")).toBe("cedar");
    expect(cartId("cedar", A)).toBe(`cedar.${A}`);
  });
});

describe("links keep the tab's context", () => {
  test("shopHref carries a well-formed context reference alongside the language", () => {
    expect(shopHref("cedar", "en", "/cart", A)).toBe(`/cedar/cart?c=${A}`);
    expect(shopHref("cedar", "ar", "/cart", A)).toBe(`/cedar/cart?c=${A}&lang=ar`);
    expect(shopHref("cedar", "en", "/search?q=x", A)).toBe(`/cedar/search?q=x&c=${A}`);
    expect(shopHref("cedar", "en", "", "../evil")).toBe("/cedar");
    expect(shopHref("cedar", "ar")).toBe("/cedar?lang=ar");
  });
});
