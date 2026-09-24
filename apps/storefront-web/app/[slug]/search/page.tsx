import type { Metadata } from "next";

import { ProductGrid } from "@/components/ProductGrid";
import { ShopFrame } from "@/components/ShopFrame";
import { fetchProducts } from "@/lib/catalog";
import { t } from "@/lib/i18n";
import { visitorFor } from "@/lib/personal";
import { type SearchParams, contextParam, loadShop, pageNumber, single } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { shop } = await loadShop(slug, "/search", await searchParams);
  return { title: shop.name, robots: { index: false } };
}

export default async function SearchPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "/search", query);
  const q = (single(query, "q") ?? "").trim().slice(0, 120);
  const page = pageNumber(query);
  const { state: context, personal, ctx } = await visitorFor(shop.slug, contextParam(query));
  const products = q ? await fetchProducts(shop.slug, { query: q, page, capability: personal }) : { items: [], page: 1, page_size: 24, total: 0, has_more: false };
  const path = `/search?q=${encodeURIComponent(q)}`;
  return (
    <ShopFrame cartBar context={context} ctx={ctx} currentPath={`/${shop.slug}${path}${page > 1 ? `&page=${page}` : ""}`} lang={lang} query={q} shop={shop}>
      <div className="section-title"><h2>{t(lang, "searchResults", { query: q })}</h2></div>
      <ProductGrid basePath={path} ctx={ctx} emptyKey="noResults" lang={lang} page={products} slug={shop.slug} />
    </ShopFrame>
  );
}
