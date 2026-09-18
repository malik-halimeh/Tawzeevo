import type { Metadata } from "next";

import { OrderView } from "@/components/OrderView";
import { ShopFrame } from "@/components/ShopFrame";
import { t } from "@/lib/i18n";
import { type SearchParams, loadShop } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { shop, lang } = await loadShop(slug, "/order", await searchParams);
  return { title: `${t(lang, "orderTitle")} · ${shop.name}`, robots: { index: false, follow: false } };
}

/** `/{slug}/order#<reference>` — the provisional order page (D-046). */
export default async function OrderPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "/order", query);
  return (
    <ShopFrame currentPath={`/${shop.slug}/order`} lang={lang} shop={shop}>
      <OrderView lang={lang} slug={shop.slug} />
    </ShopFrame>
  );
}
