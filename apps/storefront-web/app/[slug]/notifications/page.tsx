import type { Metadata } from "next";

import { NotificationsView } from "@/components/Notifications";
import { ShopFrame } from "@/components/ShopFrame";
import { t } from "@/lib/i18n";
import { visitorFor } from "@/lib/personal";
import { type SearchParams, contextParam, loadShop } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { shop, lang } = await loadShop(slug, "/notifications", await searchParams);
  return { title: `${t(lang, "notifications")} · ${shop.name}`, robots: { index: false, follow: false } };
}

/** `/{slug}/notifications` — the personalized customer's notifications (D-114). */
export default async function NotificationsPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "/notifications", query);
  const { state: context, ctx } = await visitorFor(shop.slug, contextParam(query));
  return (
    <ShopFrame context={context} ctx={ctx} currentPath={`/${shop.slug}/notifications`} lang={lang} shop={shop}>
      <header className="page-head">
        <h2>{t(lang, "notifications")}</h2>
        <p>{t(lang, "notificationsLead")}</p>
      </header>
      <NotificationsView ctx={context?.granted ? ctx : null} lang={lang} slug={shop.slug} />
    </ShopFrame>
  );
}
