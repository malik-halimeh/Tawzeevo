import type { Metadata } from "next";
import Link from "next/link";

import { ProductCard, ProductGrid } from "@/components/ProductGrid";
import { ShopFrame } from "@/components/ShopFrame";
import { fetchFeatured, fetchProducts, fetchRecommended } from "@/lib/catalog";
import { shopHref } from "@/lib/format";
import { t } from "@/lib/i18n";
import { capabilityFor, resolveContext } from "@/lib/personal";
import { type SearchParams, loadShop, pageNumber } from "@/lib/shop";

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
  const capability = await capabilityFor(shop.slug);
  const context = await resolveContext(capability);
  const personal = context ? capability : null;
  const [products, featured, recommended] = await Promise.all([
    fetchProducts(shop.slug, { page, capability: personal }),
    page === 1 ? fetchFeatured(shop.slug, personal) : Promise.resolve({ items: [] }),
    page === 1 ? fetchRecommended(shop.slug, 8, personal) : Promise.resolve({ items: [] }),
  ]);
  return (
    <ShopFrame context={context} currentPath={`/${shop.slug}${page > 1 ? `?page=${page}` : ""}`} lang={lang} shop={shop}>
      {shop.categories.length > 0 ? (
        <>
          <h2>{t(lang, "categories")}</h2>
          <ul className="chips">
            <li><Link aria-current="page" href={shopHref(shop.slug, lang)}>{t(lang, "allProducts")}</Link></li>
            {shop.categories.map((category) => (
              <li key={category.id}>
                <Link href={shopHref(shop.slug, lang, `/c/${category.id}`)}>{lang === "ar" ? category.name_ar : category.name_en} · {category.product_count}</Link>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {featured.items.length > 0 ? (
        <section aria-labelledby="featured-title">
          <h2 id="featured-title">{t(lang, "featured")}</h2>
          <ul className="grid">{featured.items.map((product) => <ProductCard key={`f-${product.id}`} lang={lang} product={product} slug={shop.slug} />)}</ul>
        </section>
      ) : null}
      {recommended.items.length > 0 ? (
        <section aria-labelledby="recommended-title">
          <h2 id="recommended-title">{t(lang, "recommended")}</h2>
          <ul className="grid">{recommended.items.map((product) => <ProductCard key={`r-${product.id}`} lang={lang} product={product} slug={shop.slug} />)}</ul>
        </section>
      ) : null}
      <h2>{t(lang, "allProducts")}</h2>
      <ProductGrid basePath="" emptyKey="noProducts" lang={lang} page={products} slug={shop.slug} />
    </ShopFrame>
  );
}
