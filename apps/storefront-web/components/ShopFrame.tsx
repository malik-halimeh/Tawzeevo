import Link from "next/link";
import type { ReactNode } from "react";

import type { PublicStorefront } from "@/lib/catalog";
import type { CustomerContext } from "@/lib/personal";
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
  const switchHref = other === "ar" ? `${currentPath}${currentPath.includes("?") ? "&" : "?"}lang=ar` : currentPath.replace(/([?&])lang=ar(&|$)/, (_m, p1: string, p2: string) => (p2 ? p1 : "")).replace(/\?$/, "");
  return (
    <div lang={lang} dir={dirFor(lang)}>
      <a className="skip-link" href="#content">{t(lang, "skipToContent")}</a>
      <header className="shop-header">
        <h1><Link href={shopHref(shop.slug, lang)}>{shop.name}</Link></h1>
        <nav aria-label={t(lang, "storefront")}>
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
        {children}
      </main>
      <footer className="shop-footer">{t(lang, "poweredBy")}</footer>
    </div>
  );
}
