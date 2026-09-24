import Link from "next/link";
import type { ReactNode } from "react";

import { type PublicStorefront, publicApiBase } from "@/lib/catalog";
import type { CustomerContext } from "@/lib/personal";
import { CartBar, CartLink } from "./CartControls";
import { Icon } from "./Icon";
import { PersonalBanner } from "./PersonalBanner";
import { CONTEXT_PARAM, isContextRef, shopHref } from "@/lib/format";
import { type Lang, dirFor, otherLang, t } from "@/lib/i18n";
import { themeTokens } from "@/lib/theme";

/**
 * Shared shop chrome: name, search, language switch, the "not accepting orders" notice, footer.
 * `lang`/`dir` are set here so every page under a shop renders in the visitor's language. The
 * business's colours arrive as validated CSS tokens only (lib/theme.ts); the layout stays ours.
 * `ctx` is the tab's personalized context reference; every shop link keeps it (D-090).
 */
export function ShopFrame({
  shop,
  lang,
  currentPath,
  query,
  context,
  ctx = null,
  cartBar = false,
  children,
}: {
  shop: PublicStorefront;
  lang: Lang;
  currentPath: string;
  query?: string | undefined;
  context?: CustomerContext | null | undefined;
  ctx?: string | null;
  cartBar?: boolean;
  children: ReactNode;
}) {
  const other = otherLang(lang);
  const brand = shop.branding ?? null;
  const title = brand?.storefront_title || shop.name;
  const theme = themeTokens(brand?.primary_color, brand?.secondary_color);
  const info = (["about_text", "contact_text", "privacy_text", "terms_text"] as const).filter((key) => brand?.[key]);
  const apiBase = publicApiBase();
  const pinnedPath = isContextRef(ctx) ? `${currentPath}${currentPath.includes("?") ? "&" : "?"}${CONTEXT_PARAM}=${ctx}` : currentPath;
  const switchHref = other === "ar" ? `${pinnedPath}${pinnedPath.includes("?") ? "&" : "?"}lang=ar` : pinnedPath.replace(/([?&])lang=ar(&|$)/, (_m, p1: string, p2: string) => (p2 ? p1 : "")).replace(/\?$/, "");
  return (
    <div className="shop" lang={lang} dir={dirFor(lang)} style={theme}>
      <a className="skip-link" href="#content">{t(lang, "skipToContent")}</a>
      <header className="shop-header">
        <div className="shop-identity">
          {brand?.logo_path ? <img alt="" className="shop-logo" src={`${apiBase}${brand.logo_path}`} /> : <span className="shop-monogram" aria-hidden="true">{title.trim().slice(0, 1)}</span>}
          <div>
            <h1><Link href={shopHref(shop.slug, lang, "", ctx)}>{title}</Link></h1>
            {brand?.description ? <span className="shop-tagline">{brand.description}</span> : null}
          </div>
        </div>
        <nav aria-label={t(lang, "storefront")} className="shop-nav">
          <CartLink ctx={ctx} lang={lang} slug={shop.slug} />
          <Link className="lang" href={switchHref} hrefLang={other} lang={other}>{t(lang, "language")}</Link>
        </nav>
        <form action={`/${shop.slug}/search`} className="search-form" method="get" role="search">
          {isContextRef(ctx) ? <input name={CONTEXT_PARAM} type="hidden" value={ctx} /> : null}
          {lang === "ar" ? <input name="lang" type="hidden" value="ar" /> : null}
          <div className="search-field">
            <Icon name="search" />
            <input aria-label={t(lang, "search")} defaultValue={query ?? ""} inputMode="search" maxLength={120} name="q" placeholder={t(lang, "searchPlaceholder")} type="search" />
          </div>
          <button type="submit">{t(lang, "search")}</button>
        </form>
      </header>
      <main id="content" tabIndex={-1}>
        {context ? <PersonalBanner ctx={ctx} displayName={context.display_name} granted={context.granted} lang={lang} slug={shop.slug} /> : null}
        {!shop.accepting_orders ? <p className="notice warn" role="status">{t(lang, "notAccepting")}</p> : null}
        {brand?.banner_text && currentPath === `/${shop.slug}` ? <p className="brand-banner">{brand.banner_text}</p> : null}
        {children}
      </main>
      {cartBar ? <CartBar ctx={ctx} lang={lang} slug={shop.slug} /> : null}
      <footer className="shop-footer">
        {brand?.phone || brand?.whatsapp || brand?.email || brand?.address ? (
          <p className="brand-contact">
            {brand.phone ? <a dir="ltr" href={`tel:${brand.phone}`}>{brand.phone}</a> : null}
            {brand.whatsapp ? <> · <a dir="ltr" href={`https://wa.me/${brand.whatsapp.replace(/\D/g, "")}`} rel="noreferrer" target="_blank">WhatsApp</a></> : null}
            {brand.email ? <> · <a dir="ltr" href={`mailto:${brand.email}`}>{brand.email}</a></> : null}
            {brand.address ? <> · {brand.address}</> : null}
          </p>
        ) : null}
        {Object.keys(brand?.social_links ?? {}).length ? (
          <p className="brand-social">{Object.entries(brand!.social_links).map(([key, url]) => <a href={url} key={key} rel="noreferrer" target="_blank">{key}</a>)}</p>
        ) : null}
        {info.length ? (
          <nav aria-label={t(lang, "aboutNav")} className="brand-pages">
            {info.map((key) => <Link href={shopHref(shop.slug, lang, `/info/${key.replace("_text", "")}`, ctx)} key={key}>{t(lang, `info_${key.replace("_text", "")}` as "info_about")}</Link>)}
          </nav>
        ) : null}
        <p className="powered"><span className="brand"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span></span>{t(lang, "poweredBy")}</p>
      </footer>
    </div>
  );
}
