import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ShopFrame } from "@/components/ShopFrame";
import { ViewBeacon } from "@/components/ViewBeacon";
import { CatalogError, type PublicProduct, fetchProduct, publicApiBase } from "@/lib/catalog";
import { priceLine, productName, secondaryPriceLine, shopHref } from "@/lib/format";
import { t } from "@/lib/i18n";
import { type SearchParams, loadShop } from "@/lib/shop";

type Props = { params: Promise<{ slug: string; productId: string }>; searchParams: Promise<SearchParams> };

async function loadProduct(slug: string, productId: string): Promise<PublicProduct> {
  try {
    return await fetchProduct(slug, productId);
  } catch (error) {
    if (error instanceof CatalogError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug, productId } = await params;
  const { shop, lang } = await loadShop(slug, `/p/${productId}`, await searchParams);
  const product = await loadProduct(shop.slug, productId);
  return { title: `${productName(product, lang)} · ${shop.name}`, description: priceLine(product, lang) };
}

export default async function ProductPage({ params, searchParams }: Props) {
  const { slug, productId } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, `/p/${productId}`, query);
  const product = await loadProduct(shop.slug, productId);
  const category = shop.categories.find((row) => row.id === product.category_id);
  const name = productName(product, lang);
  const image = product.images[0];
  const secondary = secondaryPriceLine(product, lang);
  return (
    <ShopFrame currentPath={`/${shop.slug}/p/${productId}`} lang={lang} shop={shop}>
      <ViewBeacon productId={product.id} slug={shop.slug} />
      <p><Link href={shopHref(shop.slug, lang)}>{t(lang, "backToShop")}</Link></p>
      <article className="product" aria-labelledby="product-name">
        <div className="gallery">
          {image ? <img alt={image.alt_text ?? name} height={image.height} src={`${publicApiBase()}${image.url}`} width={image.width} /> : <div className="thumb" aria-hidden="true">{name.slice(0, 1)}</div>}
        </div>
        <div className="facts">
          <h2 id="product-name">{name}</h2>
          <p className="price">{priceLine(product, lang)}</p>
          {secondary ? <p className="muted">{secondary}</p> : null}
          <dl>
            {category ? <><dt>{t(lang, "categories")}</dt><dd><Link href={shopHref(shop.slug, lang, `/c/${category.id}`)}>{lang === "ar" ? category.name_ar : category.name_en}</Link></dd></> : null}
            {product.barcode ? <><dt>{t(lang, "barcode")}</dt><dd dir="ltr">{product.barcode}</dd></> : null}
          </dl>
        </div>
      </article>
    </ShopFrame>
  );
}
