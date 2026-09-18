import Link from "next/link";

import type { PublicProduct, PublicProductPage } from "@/lib/catalog";
import { publicApiBase } from "@/lib/catalog";
import { priceLine, productName, secondaryPriceLine, shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";

export function ProductCard({ slug, product, lang }: { slug: string; product: PublicProduct; lang: Lang }) {
  const image = product.images[0];
  const name = productName(product, lang);
  return (
    <li className="card">
      <Link href={shopHref(slug, lang, `/p/${product.id}`)}>
        <div className="thumb" aria-hidden={image ? undefined : true}>
          {image ? <img alt={image.alt_text ?? name} height={image.height} loading="lazy" src={`${publicApiBase()}${image.url}`} width={image.width} /> : <span>{name.slice(0, 1)}</span>}
        </div>
        <div className="body">
          <span className="name">{name}</span>
          <span className="price">{priceLine(product, lang)}</span>
          {secondaryPriceLine(product, lang) ? <span className="sub">{secondaryPriceLine(product, lang)}</span> : null}
        </div>
      </Link>
    </li>
  );
}

export function ProductGrid({ slug, page, lang, basePath, emptyKey }: { slug: string; page: PublicProductPage; lang: Lang; basePath: string; emptyKey: "noProducts" | "noResults" }) {
  if (page.items.length === 0) return <p className="empty">{t(lang, emptyKey)}</p>;
  const join = basePath.includes("?") ? "&" : "?";
  const pageHref = (number: number) => shopHref(slug, lang, `${basePath}${join}page=${number}`);
  return (
    <>
      <p className="muted">{t(lang, "products", { count: page.total })}</p>
      <ul className="grid">
        {page.items.map((product) => <ProductCard key={product.id} lang={lang} product={product} slug={slug} />)}
      </ul>
      {page.total > page.page_size ? (
        <nav aria-label={t(lang, "page", { page: page.page })} className="pager">
          <Link aria-disabled={page.page <= 1} href={pageHref(Math.max(1, page.page - 1))} rel="prev">{t(lang, "previous")}</Link>
          <span className="muted">{t(lang, "page", { page: page.page })}</span>
          <Link aria-disabled={!page.has_more} href={pageHref(page.page + 1)} rel="next">{t(lang, "next")}</Link>
        </nav>
      ) : null}
    </>
  );
}
