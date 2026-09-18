"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { PublicProduct } from "@/lib/catalog";
import { addToCart, cartCount, onCartChange } from "@/lib/cart";
import { productName, shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";

/** Header link with the live item count. */
export function CartLink({ slug, lang }: { slug: string; lang: Lang }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const refresh = () => setCount(cartCount(slug));
    const id = window.setTimeout(refresh, 0); // read localStorage only on the client
    const off = onCartChange(refresh);
    return () => { window.clearTimeout(id); off(); };
  }, [slug]);
  return (
    <Link className="lang cart-link" href={shopHref(slug, lang, "/cart")}>
      {t(lang, "cart")}{count > 0 ? ` · ${count}` : ""}
    </Link>
  );
}

/** "Add to cart" for one product; piece by default, box when the product is sold by the box. */
export function AddToCart({ slug, product, lang, compact = false }: { slug: string; product: PublicProduct; lang: Lang; compact?: boolean }) {
  const [added, setAdded] = useState(false);
  const basis = product.price_basis;
  const add = () => {
    addToCart(slug, { product_id: product.id, name: productName(product, lang), price_basis: basis, unit_label: basis === "BOX" ? t(lang, "box") : t(lang, "piece") }, 1);
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1500);
  };
  return (
    <button className={compact ? "add-compact" : "add-button"} onClick={add} type="button">
      {added ? t(lang, "added") : t(lang, "addToCart")}
    </button>
  );
}
