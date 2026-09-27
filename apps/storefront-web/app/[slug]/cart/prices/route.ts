import { NextResponse } from "next/server";

import { CatalogError, type PublicProduct, fetchProduct, isValidSlug } from "@/lib/catalog";
import { CONTEXT_HEADER, isContextRef } from "@/lib/format";
import { visitorFor } from "@/lib/personal";

const PRODUCT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_PRODUCTS = 100;

/**
 * The prices this visitor is shown for the products in their cart (D-102): the same catalog answers
 * the product pages render, personalized when the tab's link is granted, public otherwise. Products
 * no longer published are simply absent. Nothing is stored; the shop still prices the order.
 */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isValidSlug(slug)) return NextResponse.json({ detail: { code: "STOREFRONT_NOT_FOUND" } }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { product_ids?: unknown };
  const ids = Array.isArray(body.product_ids) ? [...new Set(body.product_ids.filter((id): id is string => typeof id === "string" && PRODUCT_ID.test(id)))] : [];
  if (ids.length > MAX_PRODUCTS) return NextResponse.json({ detail: { code: "TOO_MANY_PRODUCTS" } }, { status: 422 });
  const ref = request.headers.get(CONTEXT_HEADER);
  // Only the context this tab names is used; a tab without one sees public prices (as at checkout).
  const personal = isContextRef(ref) ? (await visitorFor(slug, ref)).personal : null;
  const found = await Promise.all(ids.map(async (id): Promise<PublicProduct | null> => {
    try {
      return await fetchProduct(slug, id, personal);
    } catch (error) {
      if (error instanceof CatalogError && error.status === 404) return null;
      throw error;
    }
  }));
  const products = Object.fromEntries(found.filter((product): product is PublicProduct => product !== null).map((product) => [product.id, {
    id: product.id,
    name: product.name,
    name_ar: product.name_ar,
    currency: product.currency,
    pricing: product.pricing,
    piece_price: product.packaging.piece_price,
    box_price: product.packaging.box_price,
  }]));
  return NextResponse.json({ products }, { headers: { "Cache-Control": "no-store" } });
}
