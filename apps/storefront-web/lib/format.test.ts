import { describe, expect, test } from "vitest";

import type { PublicProduct } from "./catalog";
import { isValidSlug } from "./catalog";
import { money, priceLine, productName, secondaryPriceLine, shopHref } from "./format";
import { dirFor, normalizeLang, otherLang, t } from "./i18n";

const product: PublicProduct = {
  id: "p1", category_id: "c1", name: "Cedar Water", name_ar: "مياه الأرز", barcode: "5280000000012",
  currency: "USD", price: "12.5000", price_basis: "PIECE",
  packaging: { pieces_per_box: 12, piece_price: "12.5000", box_price: "150.0000" }, images: [],
};

describe("storefront formatting", () => {
  test("money shows the server amount without arithmetic and trims only zero decimals", () => {
    expect(money("12.5000", "USD")).toBe("12.50 USD");
    expect(money("1234567.1234", "LBP")).toBe("1,234,567.1234 LBP");
    expect(money("150.0000", "USD")).toBe("150.00 USD");
    expect(money("3", "USD")).toBe("3 USD");
  });

  test("piece and box lines follow the price basis", () => {
    expect(priceLine(product, "en")).toBe("12.50 USD per piece");
    expect(secondaryPriceLine(product, "en")).toBe("150.00 USD per box of 12");
    const boxed: PublicProduct = { ...product, price: "150.0000", price_basis: "BOX" };
    expect(priceLine(boxed, "ar")).toBe("150.00 USD للصندوق (12 قطعة)");
    expect(secondaryPriceLine(boxed, "en")).toBe("12.50 USD per piece");
    expect(secondaryPriceLine({ ...product, packaging: { pieces_per_box: null, piece_price: "12.5000", box_price: null } }, "en")).toBeNull();
  });

  test("names, language and direction", () => {
    expect(productName(product, "en")).toBe("Cedar Water");
    expect(productName(product, "ar")).toBe("مياه الأرز");
    expect(productName({ ...product, name_ar: null }, "ar")).toBe("Cedar Water");
    expect(normalizeLang("ar")).toBe("ar");
    expect(normalizeLang("fr")).toBe("en");
    expect(dirFor("ar")).toBe("rtl");
    expect(otherLang("en")).toBe("ar");
    expect(t("ar", "products", { count: 3 })).toBe("3 منتج");
    expect(t("en", "searchResults", { query: "cedar" })).toBe("Results for “cedar”");
  });

  test("links stay inside the shop and keep Arabic", () => {
    expect(shopHref("cedar-van", "en")).toBe("/cedar-van");
    expect(shopHref("cedar-van", "ar", "/p/p1")).toBe("/cedar-van/p/p1?lang=ar");
    expect(shopHref("cedar-van", "ar", "/search?q=x")).toBe("/cedar-van/search?q=x&lang=ar");
    expect(isValidSlug("cedar-van")).toBe(true);
    expect(isValidSlug("ab")).toBe(false);
    expect(isValidSlug("Has Space")).toBe(false);
    expect(isValidSlug("-lead")).toBe(false);
  });
});
