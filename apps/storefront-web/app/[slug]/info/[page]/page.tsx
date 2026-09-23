import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ShopFrame } from "@/components/ShopFrame";
import { t } from "@/lib/i18n";
import { type SearchParams, loadShop } from "@/lib/shop";

const PAGES = { about: "about_text", contact: "contact_text", privacy: "privacy_text", terms: "terms_text" } as const;
type PageKey = keyof typeof PAGES;
type Props = { params: Promise<{ slug: string; page: string }>; searchParams: Promise<SearchParams> };

/** Owner-written About / Contact / Privacy / Terms text (PHASE_08.md F), plain text only. */
export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug, page } = await params;
  const { shop, lang } = await loadShop(slug, `/info/${page}`, await searchParams);
  return { title: `${t(lang, `info_${page}` as "info_about")} · ${shop.branding?.storefront_title || shop.name}` };
}

export default async function InfoPage({ params, searchParams }: Props) {
  const { slug, page } = await params;
  if (!(page in PAGES)) notFound();
  const { shop, lang } = await loadShop(slug, `/info/${page}`, await searchParams);
  const text = shop.branding?.[PAGES[page as PageKey]];
  if (!text) notFound();
  return (
    <ShopFrame currentPath={`/${shop.slug}/info/${page}`} lang={lang} shop={shop}>
      <article className="info-page">
        <p className="eyebrow">{t(lang, "aboutNav")}</p>
        <h2>{t(lang, `info_${page}` as "info_about")}</h2>
        {text.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
      </article>
    </ShopFrame>
  );
}
