import type { Metadata } from "next";

import { AccessEntry } from "@/components/AccessEntry";
import { ShopFrame } from "@/components/ShopFrame";
import { type SearchParams, loadShop } from "@/lib/shop";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<SearchParams> };

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { shop } = await loadShop(slug, "/access", await searchParams);
  return { title: shop.name, robots: { index: false, follow: false } };
}

/** The owner's personalized link lands here: `/{slug}/access#<secret>`. The fragment never reaches
 * the server; the client component exchanges it for the HttpOnly cookie and strips it. */
export default async function AccessPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const query = await searchParams;
  const { shop, lang } = await loadShop(slug, "/access", query);
  return (
    <ShopFrame currentPath={`/${shop.slug}/access`} lang={lang} shop={shop}>
      <AccessEntry lang={lang} slug={shop.slug} />
    </ShopFrame>
  );
}
