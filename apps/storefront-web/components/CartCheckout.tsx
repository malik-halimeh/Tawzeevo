"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { type CartLine, checkoutKey, clearCart, readCart, resetCheckoutKey, setQuantity } from "@/lib/cart";
import { shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";

/**
 * Cart + guest checkout (PHASE_05.md E). Mandatory name, phone, address; the server prices every
 * line, creates the RECEIVED order and returns the provisional page. One Idempotency-Key per
 * attempt: a retry after a lost response returns the same order, never a duplicate.
 */
export function CartCheckout({ slug, lang, acceptingOrders }: { slug: string; lang: Lang; acceptingOrders: boolean }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => { const id = window.setTimeout(() => setLines(readCart(slug)), 0); return () => window.clearTimeout(id); }, [slug]);

  const change = (line: CartLine, quantity: number) => setLines(setQuantity(slug, line.product_id, line.price_basis, quantity));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(undefined);
    const key = checkoutKey(slug);
    fetch(`/${slug}/checkout/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify({
        contact_name: name.trim(),
        contact_phone: phone.trim(),
        contact_address: address.trim(),
        notes: notes.trim() || null,
        items: lines.map((line) => ({ product_id: line.product_id, quantity: String(line.quantity), price_basis: line.price_basis })),
      }),
    })
      .then(async (response) => {
        const body = (await response.json().catch(() => ({}))) as { provisional_path?: string; detail?: { code?: string; message?: string } };
        if (!response.ok || !body.provisional_path) {
          const code = body.detail?.code ?? "";
          setError(code === "STOREFRONT_NOT_ACCEPTING" ? t(lang, "notAccepting") : code === "INVALID_PHONE" ? t(lang, "invalidPhone") : code === "PRODUCT_NOT_AVAILABLE" ? t(lang, "productUnavailable") : t(lang, "checkoutFailed"));
          setBusy(false);
          return;
        }
        clearCart(slug); resetCheckoutKey(slug);
        const path = body.provisional_path;
        window.location.assign(lang === "ar" ? path.replace("#", "?lang=ar#") : path);
      })
      .catch(() => { setError(t(lang, "checkoutFailed")); setBusy(false); });
  };

  if (lines.length === 0) {
    return <p className="empty">{t(lang, "cartEmpty")} <Link href={shopHref(slug, lang)}>{t(lang, "backToShop")}</Link></p>;
  }
  return (
    <div className="checkout">
      <ul className="cart-lines" aria-label={t(lang, "cart")}>
        {lines.map((line) => (
          <li key={`${line.product_id}-${line.price_basis}`}>
            <span className="name">{line.name} <small className="muted">· {line.unit_label}</small></span>
            <span className="qty">
              <button aria-label={t(lang, "decrease")} onClick={() => change(line, line.quantity - 1)} type="button">−</button>
              <input aria-label={t(lang, "quantity")} inputMode="numeric" min={1} onChange={(event) => change(line, Math.max(1, Number(event.target.value) || 1))} type="number" value={line.quantity} />
              <button aria-label={t(lang, "increase")} onClick={() => change(line, line.quantity + 1)} type="button">+</button>
              <button className="link-button" onClick={() => change(line, 0)} type="button">{t(lang, "remove")}</button>
            </span>
          </li>
        ))}
      </ul>
      <p className="muted">{t(lang, "pricesAtCheckout")}</p>
      {!acceptingOrders ? <p className="notice" role="status">{t(lang, "notAccepting")}</p> : (
        <form className="checkout-form" onSubmit={submit}>
          <h2>{t(lang, "yourDetails")}</h2>
          <label>{t(lang, "name")}<input autoComplete="name" maxLength={200} required value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>{t(lang, "phone")}<input autoComplete="tel" dir="ltr" inputMode="tel" maxLength={64} required value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
          <label>{t(lang, "address")}<input autoComplete="street-address" maxLength={500} required value={address} onChange={(event) => setAddress(event.target.value)} /></label>
          <label>{t(lang, "notes")}<textarea maxLength={1000} rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          {error ? <p className="notice" role="alert">{error}</p> : null}
          <button className="add-button" disabled={busy} type="submit">{busy ? t(lang, "sending") : t(lang, "placeOrder")}</button>
          <p className="muted">{t(lang, "orderNote")}</p>
        </form>
      )}
    </div>
  );
}
