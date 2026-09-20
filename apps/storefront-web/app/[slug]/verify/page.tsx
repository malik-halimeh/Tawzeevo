import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ShopFrame } from "@/components/ShopFrame";
import { VerifyForm } from "@/components/VerifyForm";
import { shopHref } from "@/lib/format";
import { visitorFor } from "@/lib/personal";
import { type SearchParams, loadShop } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { shop } = await loadShop(slug, "/verify", await searchParams);
  return { title: shop.name, robots: { index: false, follow: false } };
}

/** "Verify it's you" (P9-M5): offered only to a link holder whose business asks for VERIFIED. */
export default async function VerifyPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "/verify", query);
  const { state } = await visitorFor(shop.slug);
  if (!state) redirect(shopHref(shop.slug, lang, "/access"));
  if (state.granted) redirect(shopHref(shop.slug, lang));
  return (
    <ShopFrame context={state} currentPath={`/${shop.slug}/verify`} lang={lang} shop={shop}>
      <VerifyForm contactHint={state.contact_hint} displayName={state.display_name} lang={lang} slug={shop.slug} />
    </ShopFrame>
  );
}
