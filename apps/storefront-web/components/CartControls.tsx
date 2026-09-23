"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { PublicProduct } from "@/lib/catalog";
import { addToCart, cartCount, onCartChange } from "@/lib/cart";
import { productName, shopHref } from "@/lib/format";
import { type Lang, plural, t } from "@/lib/i18n";
import { Arrow, Icon } from "./Icon";

/** The live item count is read from this browser's storage only, after mount. */
function useCartCount(slug: string): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const refresh = () => setCount(cartCount(slug));
    const id = window.setTimeout(refresh, 0); // read localStorage only on the client
    const off = onCartChange(refresh);
    return () => { window.clearTimeout(id); off(); };
  }, [slug]);
  return count;
}

/** Header link with the live item count. */
export function CartLink({ slug, lang }: { slug: string; lang: Lang }) {
  const count = useCartCount(slug);
  return (
    <Link className="cart-link" href={shopHref(slug, lang, "/cart")}>
      <Icon name="bag" />
      <span className="cart-label">{t(lang, "cart")}</span>
      {count > 0 ? <span className="cart-count">{count}</span> : null}
    </Link>
  );
}

/** Floating basket bar shown on catalog pages while the cart holds something. */
export function CartBar({ slug, lang }: { slug: string; lang: Lang }) {
  const count = useCartCount(slug);
  useEffect(() => {
    document.body.classList.toggle("cart-bar-open", count > 0);
    return () => document.body.classList.remove("cart-bar-open");
  }, [count]);
  if (count === 0) return null;
  return (
    <Link className="shop-cartbar" href={shopHref(slug, lang, "/cart")}>
      <span className="cartbar-copy">
        <span className="cart-count" aria-hidden="true">{count}</span>
        <span><strong>{t(lang, "reviewCart")}</strong><small>{plural(lang, "items", count)}</small></span>
      </span>
      <Arrow />
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
  const label = added ? t(lang, "added") : t(lang, "addToCart");
  if (compact) {
    return (
      <button aria-label={label} className={`icon-btn add-compact${added ? " added" : ""}`} onClick={add} type="button">
        <Icon name={added ? "check" : "plus"} />
        <span className="sr-only" role="status">{added ? label : ""}</span>
      </button>
    );
  }
  // The label change alone is not announced; a status message (outside the button, so its name stays single) is.
  return (
    <>
      <button className="button add-button" onClick={add} type="button">
        <Icon name={added ? "check" : "plus"} small />
        {label}
      </button>
      <span className="sr-only" role="status">{added ? label : ""}</span>
    </>
  );
}
