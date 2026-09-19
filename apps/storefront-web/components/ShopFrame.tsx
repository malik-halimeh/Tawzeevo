import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import { type PublicStorefront, publicApiBase } from "@/lib/catalog";
import type { CustomerContext } from "@/lib/personal";
import { CartLink } from "./CartControls";
import { PersonalBanner } from "./PersonalBanner";
import { shopHref } from "@/lib/format";
import { type Lang, dirFor, otherLang, t } from "@/lib/i18n";

/**
 * Shared shop chrome: name, search, language switch, the "not accepting orders" notice, footer.
 * `lang`/`dir` are set here so every page under a shop renders in the visitor's language.
 */
export function ShopFrame({
  shop,
  lang,
  currentPath,
  query,
  context,
  children,
}: {
  shop: PublicStorefront;
  lang: Lang;
  currentPath: string;
  query?: string | undefined;
  context?: CustomerContext | null | undefined;
  children: ReactNode;
}) {
  const other = otherLang(lang);
  const brand = shop.branding ?? null;
  const title = brand?.storefront_title || shop.name;
  const theme = brand?.primary_color || brand?.secondary_color
    ? ({ ...(brand?.primary_color ? { "--accent": brand.primary_color } : {}), ...(brand?.secondary_color ? { "--accent-soft": brand.secondary_color } : {}) } as CSSProperties)
    : undefined;
  const info = (["about_text", "contact_text", "privacy_text", "terms_text"] as const).filter((key) => brand?.[key]);
  const apiBase = publicApiBase();
  const switchHref = other === "ar" ? `${currentPath}${currentPath.includes("?") ? "&" : "?"}lang=ar` : currentPath.replace(/([?&])lang=ar(&|$)/, (_m, p1: string, p2: string) => (p2 ? p1 : "")).replace(/\?$/, "");
  return (
    <div lang={lang} dir={dirFor(lang)} style={theme}>
      <a className="skip-link" href="#content">{t(lang, "skipToContent")}</a>
      <header className="shop-header">
        <h1><Link href={shopHref(shop.slug, lang)}>{brand?.logo_path ? <img alt="" className="shop-logo" src={`${apiBase}${brand.logo_path}`} /> : null}{title}</Link></h1>
        <nav aria-label={t(lang, "storefront")}>
          <CartLink lang={lang} slug={shop.slug} />
          <Link className="lang" href={switchHref} hrefLang={other} lang={other}>{t(lang, "language")}</Link>
        </nav>
        <form action={`/${shop.slug}/search`} className="search-form" method="get" role="search">
          {lang === "ar" ? <input name="lang" type="hidden" value="ar" /> : null}
          <input aria-label={t(lang, "search")} defaultValue={query ?? ""} inputMode="search" maxLength={120} name="q" placeholder={t(lang, "searchPlaceholder")} type="search" />
          <button type="submit">{t(lang, "search")}</button>
        </form>
      </header>
      <main id="content">
        {context ? <PersonalBanner displayName={context.display_name} lang={lang} slug={shop.slug} /> : null}
        {!shop.accepting_orders ? <p className="notice" role="status">{t(lang, "notAccepting")}</p> : null}
        {brand?.banner_text && currentPath === `/${shop.slug}` ? <p className="brand-banner">{brand.banner_text}</p> : null}
        {children}
      </main>
      <footer className="shop-footer">
        {brand?.description ? <p>{brand.description}</p> : null}
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
            {info.map((key) => <Link href={shopHref(shop.slug, lang, `/info/${key.replace("_text", "")}`)} key={key}>{t(lang, `info_${key.replace("_text", "")}` as "info_about")}</Link>)}
          </nav>
        ) : null}
        <p>{t(lang, "poweredBy")}</p>
      </footer>
    </div>
  );
}
