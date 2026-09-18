import type { Metadata } from "next";

import { CartCheckout } from "@/components/CartCheckout";
import { ShopFrame } from "@/components/ShopFrame";
import { t } from "@/lib/i18n";
import { capabilityFor, resolveContext } from "@/lib/personal";
import { type SearchParams, loadShop } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { shop, lang } = await loadShop(slug, "/cart", await searchParams);
  return { title: `${t(lang, "cart")} · ${shop.name}`, robots: { index: false } };
}

export default async function CartPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "/cart", query);
  const context = await resolveContext(await capabilityFor(shop.slug));
  return (
    <ShopFrame context={context} currentPath={`/${shop.slug}/cart`} lang={lang} shop={shop}>
      <h2>{t(lang, "cart")}</h2>
      <CartCheckout acceptingOrders={shop.accepting_orders} lang={lang} slug={shop.slug} />
    </ShopFrame>
  );
}
