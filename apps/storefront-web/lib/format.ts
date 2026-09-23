import type { PublicProduct } from "./catalog";
import type { Lang } from "./i18n";
import { t } from "./i18n";

/** Product name in the visitor's language with a plain fallback to the base name. */
export function productName(product: PublicProduct, lang: Lang): string {
  return lang === "ar" && product.name_ar ? product.name_ar : product.name;
}

/**
 * Money is shown exactly as the server sent it (four-decimal string), trimmed to two decimals for
 * display only when the extra decimals are zero. No arithmetic happens here.
 */
export function money(amount: string, currency: string): string {
  const [whole = "0", fraction = ""] = amount.split(".");
  const trimmed = fraction.length > 2 && /^\d\d00$/.test(fraction) ? fraction.slice(0, 2) : fraction;
  const groupedWhole = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const grouped = trimmed ? `${groupedWhole}.${trimmed}` : groupedWhole;
  return `${grouped} ${currency}`;
}

export function priceLine(product: PublicProduct, lang: Lang): string {
  if (product.price_basis === "BOX") {
    return `${money(product.price, product.currency)} ${t(lang, "perBox", { count: product.packaging.pieces_per_box ?? 0 })}`;
  }
  return `${money(product.price, product.currency)} ${t(lang, "perPiece")}`;
}

/** The other packaging's price as amount and basis, so a page can keep the amount left to right on its own. */
export function secondaryPrice(product: PublicProduct, lang: Lang): { amount: string; basis: string } | null {
  if (product.price_basis === "BOX") {
    return { amount: money(product.packaging.piece_price, product.currency), basis: t(lang, "perPiece") };
  }
  if (product.packaging.box_price && product.packaging.pieces_per_box) {
    return { amount: money(product.packaging.box_price, product.currency), basis: t(lang, "perBox", { count: product.packaging.pieces_per_box }) };
  }
  return null;
}

export function secondaryPriceLine(product: PublicProduct, lang: Lang): string | null {
  const price = secondaryPrice(product, lang);
  return price ? `${price.amount} ${price.basis}` : null;
}

/** Keeps a link inside the same shop and language. */
export function shopHref(slug: string, lang: Lang, path = ""): string {
  const base = `/${slug}${path}`;
  return lang === "ar" ? `${base}${base.includes("?") ? "&" : "?"}lang=ar` : base;
}
