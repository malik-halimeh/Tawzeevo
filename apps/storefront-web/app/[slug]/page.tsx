import type { Metadata } from "next";
import Link from "next/link";

import { ProductCard, ProductGrid } from "@/components/ProductGrid";
import { ShopFrame } from "@/components/ShopFrame";
import { fetchFeatured, fetchProducts, fetchRecommended } from "@/lib/catalog";
import { shopHref } from "@/lib/format";
import { t } from "@/lib/i18n";
import { visitorFor } from "@/lib/personal";
import { type SearchParams, contextParam, loadShop, pageNumber } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "", query);
  return { title: shop.name, description: `${shop.name} · ${t(lang, "storefront")}` };
}

export default async function ShopHome({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "", query);
  const page = pageNumber(query);
  const { state: context, personal, ctx } = await visitorFor(shop.slug, contextParam(query));
  const [products, featured, recommended] = await Promise.all([
    fetchProducts(shop.slug, { page, capability: personal }),
    page === 1 ? fetchFeatured(shop.slug, personal) : Promise.resolve({ items: [] }),
    page === 1 ? fetchRecommended(shop.slug, 8, personal) : Promise.resolve({ items: [] }),
  ]);
  return (
    <ShopFrame cartBar context={context} ctx={ctx} currentPath={`/${shop.slug}${page > 1 ? `?page=${page}` : ""}`} lang={lang} shop={shop}>
      {shop.categories.length > 0 ? (
        <nav aria-label={t(lang, "categories")}>
          <ul className="chips">
            <li><Link aria-current="page" href={shopHref(shop.slug, lang, "", ctx)}>{t(lang, "allProducts")}</Link></li>
            {shop.categories.map((category) => (
              <li key={category.id}>
                <Link href={shopHref(shop.slug, lang, `/c/${category.id}`, ctx)}>{lang === "ar" ? category.name_ar : category.name_en} · {category.product_count}</Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      {featured.items.length > 0 ? (
        <section aria-labelledby="featured-title">
          <div className="section-title"><h2 id="featured-title">{t(lang, "featured")}</h2></div>
          <ul className="grid">{featured.items.map((product) => <ProductCard ctx={ctx} key={`f-${product.id}`} lang={lang} product={product} slug={shop.slug} />)}</ul>
        </section>
      ) : null}
      {recommended.items.length > 0 ? (
        <section aria-labelledby="recommended-title">
          <div className="section-title"><h2 id="recommended-title">{t(lang, "recommended")}</h2></div>
          <ul className="grid">{recommended.items.map((product) => <ProductCard ctx={ctx} key={`r-${product.id}`} lang={lang} product={product} slug={shop.slug} />)}</ul>
        </section>
      ) : null}
      <div className="section-title"><h2>{t(lang, "allProducts")}</h2></div>
      <ProductGrid basePath="" ctx={ctx} emptyKey="noProducts" lang={lang} page={products} slug={shop.slug} />
    </ShopFrame>
  );
}
