import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ProductGrid } from "@/components/ProductGrid";
import { ShopFrame } from "@/components/ShopFrame";
import { fetchProducts } from "@/lib/catalog";
import { shopHref } from "@/lib/format";
import { t } from "@/lib/i18n";
import { type SearchParams, loadShop, pageNumber } from "@/lib/shop";

type Props = { params: Promise<{ slug: string; categoryId: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug, categoryId } = await params;
  const { shop, lang } = await loadShop(slug, `/c/${categoryId}`, await searchParams);
  const category = shop.categories.find((row) => row.id === categoryId);
  return { title: category ? `${lang === "ar" ? category.name_ar : category.name_en} · ${shop.name}` : shop.name };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { slug, categoryId } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, `/c/${categoryId}`, query);
  const category = shop.categories.find((row) => row.id === categoryId);
  if (!category) notFound();
  const page = pageNumber(query);
  const products = await fetchProducts(shop.slug, { categoryId, page });
  return (
    <ShopFrame currentPath={`/${shop.slug}/c/${categoryId}${page > 1 ? `?page=${page}` : ""}`} lang={lang} shop={shop}>
      <h2>{t(lang, "categories")}</h2>
      <ul className="chips">
        <li><Link href={shopHref(shop.slug, lang)}>{t(lang, "allProducts")}</Link></li>
        {shop.categories.map((row) => (
          <li key={row.id}>
            <Link aria-current={row.id === categoryId ? "page" : undefined} href={shopHref(shop.slug, lang, `/c/${row.id}`)}>{lang === "ar" ? row.name_ar : row.name_en} · {row.product_count}</Link>
          </li>
        ))}
      </ul>
      <h2>{lang === "ar" ? category.name_ar : category.name_en}</h2>
      <ProductGrid basePath={`/c/${categoryId}`} emptyKey="noProducts" lang={lang} page={products} slug={shop.slug} />
    </ShopFrame>
  );
}
