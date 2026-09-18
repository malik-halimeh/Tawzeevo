import { notFound, permanentRedirect } from "next/navigation";

import { CatalogError, type PublicStorefront, fetchStorefront, isValidSlug } from "./catalog";
import { type Lang, normalizeLang } from "./i18n";

export type SearchParams = Record<string, string | string[] | undefined>;

export function langFrom(params: SearchParams): Lang {
  const raw = params.lang;
  return normalizeLang(Array.isArray(raw) ? raw[0] : raw);
}

export function single(params: SearchParams, key: string): string | undefined {
  const raw = params[key];
  return Array.isArray(raw) ? raw[0] : raw;
}

export function pageNumber(params: SearchParams): number {
  const raw = Number(single(params, "page") ?? "1");
  return Number.isInteger(raw) && raw >= 1 && raw <= 10_000 ? raw : 1;
}

/**
 * Resolve the shop for a route. A renamed address is redirected permanently to the canonical
 * slug (D-047) with the rest of the path and the language preserved; an unknown address is 404.
 */
export async function loadShop(slug: string, restOfPath: string, params: SearchParams): Promise<{ shop: PublicStorefront; lang: Lang }> {
  if (!isValidSlug(slug)) notFound();
  const lang = langFrom(params);
  let shop: PublicStorefront;
  try {
    shop = await fetchStorefront(slug);
  } catch (error) {
    if (error instanceof CatalogError && error.status === 404) notFound();
    throw error;
  }
  if (shop.redirected_from) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      const first = Array.isArray(value) ? value[0] : value;
      if (first !== undefined) query.set(key, first);
    }
    const suffix = query.size ? `?${query.toString()}` : "";
    permanentRedirect(`/${shop.slug}${restOfPath}${suffix}`);
  }
  return { shop, lang };
}
