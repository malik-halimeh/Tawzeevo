import Link from "next/link";

import type { PublicProduct, PublicProductPage } from "@/lib/catalog";
import { publicApiBase } from "@/lib/catalog";
import { money, productName, secondaryPrice, shopHref } from "@/lib/format";
import { type Lang, plural, t } from "@/lib/i18n";
import { AddToCart } from "./CartControls";

/** The server's price and basis, shown exactly as sent: the amount and the unit it is for. */
function basisLabel(product: PublicProduct, lang: Lang): string {
  return product.price_basis === "BOX" ? t(lang, "perBox", { count: product.packaging.pieces_per_box ?? 0 }) : t(lang, "perPiece");
}

export function ProductCard({ slug, product, lang, ctx = null }: { slug: string; product: PublicProduct; lang: Lang; ctx?: string | null }) {
  const image = product.images[0];
  const name = productName(product, lang);
  const secondary = secondaryPrice(product, lang);
  return (
    <li className="card">
      <Link href={shopHref(slug, lang, `/p/${product.id}`, ctx)}>
        <div className="thumb" aria-hidden={image ? undefined : true}>
          {image ? <img alt={image.alt_text ?? name} height={image.height} loading="lazy" src={`${publicApiBase()}${image.url}`} width={image.width} /> : <span>{name.slice(0, 1)}</span>}
        </div>
        <div className="body">
          <span className="name">{name}</span>
          {secondary ? <span className="sub"><bdi dir="ltr">{secondary.amount}</bdi> {secondary.basis}</span> : null}
        </div>
      </Link>
      <div className="card-buy">
        <span><bdi className="price" dir="ltr">{money(product.price, product.currency)}</bdi><small>{basisLabel(product, lang)}</small></span>
        <AddToCart compact ctx={ctx} lang={lang} product={product} slug={slug} />
      </div>
    </li>
  );
}

export function ProductGrid({ slug, page, lang, basePath, emptyKey, ctx = null }: { slug: string; page: PublicProductPage; lang: Lang; basePath: string; emptyKey: "noProducts" | "noResults"; ctx?: string | null }) {
  if (page.items.length === 0) return <p className="empty">{t(lang, emptyKey)}</p>;
  const join = basePath.includes("?") ? "&" : "?";
  const pageHref = (number: number) => shopHref(slug, lang, `${basePath}${join}page=${number}`, ctx);
  return (
    <>
      <p className="muted">{plural(lang, "products", page.total)}</p>
      <ul className="grid">
        {page.items.map((product) => <ProductCard ctx={ctx} key={product.id} lang={lang} product={product} slug={slug} />)}
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
