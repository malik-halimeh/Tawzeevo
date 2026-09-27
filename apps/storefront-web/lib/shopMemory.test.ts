import { beforeEach, describe, expect, test, vi } from "vitest";

import {
  ORDER_LIFETIME_MS,
  cartTotals,
  forgetContact,
  forgetOrderReference,
  keepOrderReference,
  readContact,
  readOrderReference,
  rememberContact,
  reorderLines,
} from "./shopMemory";

/** In-memory Storage, so the functions run in the node test environment exactly as in a browser. */
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

const REF = `${"a".repeat(32)}.${"B".repeat(43)}`;

beforeEach(() => {
  vi.stubGlobal("localStorage", memoryStorage());
  vi.stubGlobal("window", { dispatchEvent: () => true, addEventListener: () => undefined, removeEventListener: () => undefined });
  vi.stubGlobal("CustomEvent", class { constructor(public type: string) {} });
});

describe("remember my details (opt-in, per shop; D-102)", () => {
  test("nothing is kept until asked; remembered details come back; forgetting removes them", () => {
    expect(readContact("cedar")).toBeNull();
    rememberContact("cedar", { name: " Maya ", phone: "+961 70 123 456", address: "Hamra, near the bank" });
    expect(readContact("cedar")).toEqual({ name: "Maya", phone: "+961 70 123 456", address: "Hamra, near the bank" });
    expect(localStorage.getItem("tawzeevo.shop.cedar.contact")).not.toBeNull();
    expect(readContact("other-shop")).toBeNull(); // per shop
    forgetContact("cedar");
    expect(readContact("cedar")).toBeNull();
  });

  test("a damaged entry is ignored", () => {
    localStorage.setItem("tawzeevo.shop.cedar.contact", "{not json");
    expect(readContact("cedar")).toBeNull();
    localStorage.setItem("tawzeevo.shop.cedar.contact", JSON.stringify({ name: 1 }));
    expect(readContact("cedar")).toBeNull();
  });
});

describe("the order kept on this device for its 72-hour lifetime (D-102)", () => {
  test("valid until 72 hours after the order was created, then removed", () => {
    const created = Date.parse("2026-09-27T10:00:00Z");
    keepOrderReference("cedar", REF, created);
    expect(readOrderReference("cedar", created + 1000)).toBe(REF);
    expect(readOrderReference("cedar", created + ORDER_LIFETIME_MS - 1)).toBe(REF);
    expect(readOrderReference("cedar", created + ORDER_LIFETIME_MS)).toBeNull();
    expect(localStorage.getItem("tawzeevo.shop.cedar.order")).toBeNull(); // expired entry removed
  });

  test("only a well-formed reference is kept, and it can be forgotten", () => {
    keepOrderReference("cedar", "not-a-reference", Date.now());
    expect(readOrderReference("cedar", Date.now())).toBeNull();
    keepOrderReference("cedar", REF, Date.now());
    forgetOrderReference("cedar");
    expect(readOrderReference("cedar", Date.now())).toBeNull();
  });
});

describe("calculated total from the prices shown (D-102, D-066)", () => {
  const prices = {
    water: { currency: "USD", piece_price: "1.2500", box_price: "14.0000" },
    rice: { currency: "USD", piece_price: "3.3333", box_price: null },
    tahini: { currency: "LBP", piece_price: "250000.0000", box_price: null },
  };

  test("exact per line and per currency; currencies are never added together", () => {
    const result = cartTotals([
      { product_id: "water", price_basis: "PIECE", quantity: 3 },
      { product_id: "water", price_basis: "BOX", quantity: 2 },
      { product_id: "rice", price_basis: "PIECE", quantity: 3 },
      { product_id: "tahini", price_basis: "PIECE", quantity: 2 },
    ], prices);
    expect(result.lines.map((line) => line.line_total)).toEqual(["3.7500", "28.0000", "9.9999", "500000.0000"]);
    expect(result.totals).toEqual([{ currency: "LBP", total: "500000.0000" }, { currency: "USD", total: "41.7499" }]);
    expect(result.missing).toBe(0);
  });

  test("a product without a shown price is left out of the total and counted", () => {
    const result = cartTotals([
      { product_id: "water", price_basis: "PIECE", quantity: 1 },
      { product_id: "gone", price_basis: "PIECE", quantity: 1 },
      { product_id: "rice", price_basis: "BOX", quantity: 1 },
    ], prices);
    expect(result.totals).toEqual([{ currency: "USD", total: "1.2500" }]);
    expect(result.missing).toBe(2);
    expect(result.lines[1]).toMatchObject({ unit_price: null, line_total: null });
  });
});

describe("order these again (D-102)", () => {
  const available = {
    water: { id: "water", name: "Water", name_ar: "مياه", box_price: "14.0000" },
    rice: { id: "rice", name: "Rice", name_ar: null, box_price: null },
  };
  const labels = { piece: "piece", box: "box" };

  test("maps products and quantities; typed lines, unpublished products and lost boxes are skipped", () => {
    const { lines, skipped } = reorderLines([
      { product_id: "water", name: "Water (old name)", quantity: "2.0000", unit: "BOX" },
      { product_id: "rice", name: "Rice", quantity: "3.0000", unit: "PIECE" },
      { product_id: null, name: "Delivery tray", quantity: "1.0000", unit: "PIECE" },
      { product_id: "gone", name: "Gone", quantity: "1.0000", unit: "PIECE" },
      { product_id: "rice", name: "Rice", quantity: "1.0000", unit: "BOX" },
    ], available, "en", labels);
    expect(lines).toEqual([
      { product_id: "water", name: "Water", price_basis: "BOX", unit_label: "box", quantity: 2 },
      { product_id: "rice", name: "Rice", price_basis: "PIECE", unit_label: "piece", quantity: 3 },
    ]);
    expect(skipped).toBe(3);
  });

  test("uses the Arabic name when there is one, and at least one unit", () => {
    const { lines } = reorderLines([{ product_id: "water", name: "Water", quantity: "0.2000", unit: "PIECE" }], available, "ar", { piece: "قطعة", box: "صندوق" });
    expect(lines).toEqual([{ product_id: "water", name: "مياه", price_basis: "PIECE", unit_label: "قطعة", quantity: 1 }]);
  });
});
