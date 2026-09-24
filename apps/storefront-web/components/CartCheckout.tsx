"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";

import { type CartLine, cartId, checkoutKey, clearCart, readCart, resetCheckoutKey, setQuantity } from "@/lib/cart";
import { CONTEXT_HEADER, CONTEXT_PARAM, isContextRef, shopHref } from "@/lib/format";
import { type Lang, plural, t } from "@/lib/i18n";
import { Arrow, Icon } from "./Icon";

/**
 * Cart + checkout (PHASE_05.md E). A public visitor gives name, phone and address. A personalized
 * tab orders as its link's customer (D-090): name and phone are not asked for or sent — the server
 * takes them from the customer record — and only the address and notes stay editable. The server
 * prices every line, creates the RECEIVED order and returns the provisional page. One
 * Idempotency-Key per attempt: a retry after a lost response returns the same order, never a duplicate.
 */
export interface PersonalCheckout { displayName: string; hasSavedAddress: boolean }

export function CartCheckout({ slug, lang, acceptingOrders, ctx = null, personal = null }: { slug: string; lang: Lang; acceptingOrders: boolean; ctx?: string | null; personal?: PersonalCheckout | null }) {
  const cart = cartId(slug, ctx);
  // A link that lapsed between page load and submit turns this form into the public one in place.
  const [lapsed, setLapsed] = useState(false);
  const personalMode = personal !== null && !lapsed;
  const [lines, setLines] = useState<CartLine[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const id = useId();
  // Focus that would fall to the page — "Place order" is disabled while sending, a removed line takes its
  // button with it — goes back to the button, or to the cart list (the way back to the shop once it is empty).
  const focusNext = useRef<"submit" | "cart" | "name" | null>(null);
  const submitButton = useRef<HTMLButtonElement>(null);
  const nameInput = useRef<HTMLInputElement>(null);
  const cartList = useRef<HTMLUListElement>(null);
  const backToShop = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (!focusNext.current || busy) return;
    (focusNext.current === "submit" ? submitButton.current : focusNext.current === "name" ? nameInput.current : cartList.current ?? backToShop.current)?.focus();
    focusNext.current = null;
  });

  useEffect(() => { const timer = window.setTimeout(() => setLines(readCart(cart)), 0); return () => window.clearTimeout(timer); }, [cart]);

  const change = (line: CartLine, quantity: number) => setLines(setQuantity(cart, line.product_id, line.price_basis, quantity));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(undefined);
    const key = checkoutKey(cart);
    const items = lines.map((line) => ({ product_id: line.product_id, quantity: String(line.quantity), price_basis: line.price_basis }));
    // Identity is never sent from a personalized tab: the server takes it from the link (D-090).
    const payload = personalMode
      ? { contact_address: address.trim() || null, notes: notes.trim() || null, items }
      : { contact_name: name.trim(), contact_phone: phone.trim(), contact_address: address.trim(), notes: notes.trim() || null, items };
    fetch(`/${slug}/checkout/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": key, ...(isContextRef(ctx) ? { [CONTEXT_HEADER]: ctx } : {}) },
      body: JSON.stringify(payload),
    })
      .then(async (response) => {
        const body = (await response.json().catch(() => ({}))) as { provisional_path?: string; detail?: { code?: string; message?: string } };
        if (!response.ok || !body.provisional_path) {
          const code = body.detail?.code ?? "";
          if (code === "CONTACT_REQUIRED" && personalMode) {
            // The link is no longer active: continue as a public order, asking for the details.
            setLapsed(true);
            setError(t(lang, "personalLapsed"));
            focusNext.current = "name";
            setBusy(false);
            return;
          }
          setError(code === "STOREFRONT_NOT_ACCEPTING" ? t(lang, "notAccepting") : code === "INVALID_PHONE" ? t(lang, "invalidPhone") : code === "PRODUCT_NOT_AVAILABLE" ? t(lang, "productUnavailable") : code === "CONTACT_ADDRESS_REQUIRED" ? t(lang, "addressRequired") : t(lang, "checkoutFailed"));
          focusNext.current = "submit";
          setBusy(false);
          return;
        }
        clearCart(cart); resetCheckoutKey(cart);
        const [base, fragment = ""] = body.provisional_path.split("#");
        const query = [isContextRef(ctx) ? `${CONTEXT_PARAM}=${ctx}` : "", lang === "ar" ? "lang=ar" : ""].filter(Boolean).join("&");
        // A full load on purpose: the order reference travels in the fragment to the order page.
        window.location.assign(new URL(`${base}${query ? `?${query}` : ""}#${fragment}`, window.location.origin).href);
      })
      .catch(() => { setError(t(lang, "checkoutFailed")); focusNext.current = "submit"; setBusy(false); });
  };

  if (lines.length === 0) {
    return (
      <section className="empty">
        <Icon name="bag" />
        <p>{t(lang, "cartEmpty")}</p>
        <Link className="button" href={shopHref(slug, lang, "", ctx)} ref={backToShop}>{t(lang, "backToShop")}<Arrow small /></Link>
      </section>
    );
  }
  const total = lines.reduce((sum, line) => sum + line.quantity, 0);
  return (
    <div className="cart-layout checkout">
      <section>
        <ul className="cart-lines" aria-label={t(lang, "cart")} ref={cartList} tabIndex={-1}>
          {lines.map((line) => (
            <li key={`${line.product_id}-${line.price_basis}`}>
              <span className="name">{line.name} <small className="muted">{line.unit_label}</small></span>
              <span className="qty">
                <button aria-label={t(lang, "decrease")} onClick={() => change(line, line.quantity - 1)} type="button"><Icon name="minus" small /></button>
                <input aria-label={t(lang, "quantity")} inputMode="numeric" min={1} onChange={(event) => change(line, Math.max(1, Number(event.target.value) || 1))} type="number" value={line.quantity} />
                <button aria-label={t(lang, "increase")} onClick={() => change(line, line.quantity + 1)} type="button"><Icon name="plus" small /></button>
                <button className="link-button" onClick={() => { focusNext.current = "cart"; change(line, 0); }} type="button">{t(lang, "remove")}</button>
              </span>
            </li>
          ))}
        </ul>
        <p className="muted">{t(lang, "pricesAtCheckout")}</p>
        <Link className="text-link" href={shopHref(slug, lang, "", ctx)}><Arrow back small />{t(lang, "continueBrowsing")}</Link>
      </section>
      <aside className="cart-summary" aria-label={t(lang, "orderSummary")}>
        <h2>{t(lang, "orderSummary")}</h2>
        <p><strong>{plural(lang, "items", total)}</strong></p>
        <p className="muted">{t(lang, "checkoutLead")}</p>
        {!acceptingOrders ? <p className="notice warn" role="status">{t(lang, "notAccepting")}</p> : (
          <form className="checkout-form" onSubmit={submit}>
            <h2>{t(lang, "yourDetails")}</h2>
            {personalMode ? (
              <p className="ordering-as" data-testid="ordering-as"><strong>{t(lang, "orderingAs", { name: personal.displayName })}</strong></p>
            ) : (
              <>
                <label htmlFor={`${id}-name`}>{t(lang, "name")}<input autoComplete="name" id={`${id}-name`} maxLength={200} ref={nameInput} required value={name} onChange={(event) => setName(event.target.value)} /></label>
                <label htmlFor={`${id}-phone`}>{t(lang, "phone")}<input autoComplete="tel" dir="ltr" id={`${id}-phone`} inputMode="tel" maxLength={64} required value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
              </>
            )}
            <label htmlFor={`${id}-address`}>{t(lang, "address")}<input autoComplete="street-address" id={`${id}-address`} maxLength={500} required={!(personalMode && personal.hasSavedAddress)} value={address} onChange={(event) => setAddress(event.target.value)} /></label>
            <p className="hint">{personalMode && personal.hasSavedAddress ? t(lang, "savedAddressHint") : t(lang, "addressHint")}</p>
            <label htmlFor={`${id}-notes`}>{t(lang, "notes")}<textarea id={`${id}-notes`} maxLength={1000} rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
            {error ? <p className="notice notice-error" role="alert">{error}</p> : null}
            <button className="button" disabled={busy} ref={submitButton} type="submit">{busy ? t(lang, "sending") : t(lang, "placeOrder")}<Arrow /></button>
            <p className="muted">{t(lang, "orderNote")}</p>
          </form>
        )}
      </aside>
    </div>
  );
}
