"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { addToCart, cartId } from "@/lib/cart";
import { CONTEXT_HEADER, isContextRef, money, shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";
import { type AvailableProduct, forgetOrderReference, keepOrderReference, readOrderReference, reorderLines } from "@/lib/shopMemory";
import { Arrow, Icon } from "./Icon";

interface ProvisionalItem { product_id?: string | null; name: string; quantity: string; unit: string; pieces_per_box: number | null; unit_price: string; total: string }
interface ProvisionalOrder {
  business_name: string; status: string; contact_name: string; contact_phone: string; contact_address: string; notes: string | null;
  currency: string; created_at: string; invoice_status: string | null; official_number: string | null;
  subtotal: string; discount: string; markup: string; net_sales: string; items: ProvisionalItem[]; decision_note: string | null;
  delivery_date: string | null; cancellation: "PENDING" | "APPROVED" | "REJECTED" | null;
}

const KEY = (slug: string) => `tawzeevo.order-ref.${slug}`;

/**
 * Provisional order page (D-046, D-102): the reference arrives in the URL fragment, is kept on this
 * device for the order's 72-hour lifetime (so "Your order" in the shop header reopens it), and is
 * sent only in a private header through the shop's proxy. It shows the order as submitted — not a
 * confirmed invoice — and can put the same products back in the cart.
 */
export function OrderView({ slug, lang, ctx = null }: { slug: string; lang: Lang; ctx?: string | null }) {
  const [order, setOrder] = useState<ProvisionalOrder>();
  const [state, setState] = useState<"loading" | "missing">("loading");
  const referenceRef = useRef("");
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const [askResult, setAskResult] = useState<string>();
  const [reordering, setReordering] = useState(false);
  const [reorderNote, setReorderNote] = useState<string>();
  const reasonId = useId();
  // The request button is disabled while sending and the form is replaced once the request is sent, so focus
  // would fall to the page: it moves to the pending notice, or back to the button when the request failed.
  const focusNext = useRef<"notice" | "button" | null>(null);
  const pendingNotice = useRef<HTMLParagraphElement>(null);
  const requestButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!focusNext.current || asking) return;
    (focusNext.current === "notice" ? pendingNotice.current : requestButton.current)?.focus();
    focusNext.current = null;
  });

  const requestCancellation = () => {
    const reference = referenceRef.current;
    if (!reference) return;
    setAsking(true);
    fetch(`/${slug}/order/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reference, reason: reason.trim() || null }) })
      .then(async (response) => {
        if (!response.ok) { setAskResult(t(lang, "cancelFailed")); focusNext.current = "button"; return; }
        setAskResult(t(lang, "cancelRequested"));
        setOrder((current) => (current ? { ...current, cancellation: "PENDING" } : current));
        focusNext.current = "notice";
      })
      .catch(() => { setAskResult(t(lang, "cancelFailed")); focusNext.current = "button"; })
      .finally(() => setAsking(false));
  };

  useEffect(() => {
    let reference = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
    if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
    try {
      if (reference) sessionStorage.setItem(KEY(slug), reference);
      else reference = sessionStorage.getItem(KEY(slug)) ?? readOrderReference(slug, Date.now()) ?? "";
    } catch { /* no storage: the fragment alone must do */ }
    referenceRef.current = reference;
    const load = async () => {
      if (!reference) return null;
      const response = await fetch(`/${slug}/order/view`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reference }) });
      return response.ok ? ((await response.json()) as ProvisionalOrder) : null;
    };
    load()
      .then((result) => {
        if (result) {
          setOrder(result);
          // Kept with the order's own creation time, so it lapses with the server's 72 hours.
          keepOrderReference(slug, reference, Date.parse(result.created_at));
        } else {
          if (reference && reference === readOrderReference(slug, Date.now())) forgetOrderReference(slug);
          setState("missing");
        }
      })
      .catch(() => setState("missing"));
  }, [slug]);

  // The same products and quantities back in this tab's cart, at today's prices; lines the shop typed
  // and products no longer offered are left out with a note.
  const orderAgain = () => {
    if (!order) return;
    setReordering(true); setReorderNote(undefined);
    const ids = [...new Set(order.items.map((item) => item.product_id).filter((id): id is string => Boolean(id)))];
    fetch(`/${slug}/cart/prices`, { method: "POST", headers: { "Content-Type": "application/json", ...(isContextRef(ctx) ? { [CONTEXT_HEADER]: ctx } : {}) }, body: JSON.stringify({ product_ids: ids }) })
      .then(async (response) => (response.ok ? ((await response.json()) as { products: Record<string, AvailableProduct> }) : Promise.reject(new Error("prices"))))
      .then(({ products }) => {
        const { lines, skipped } = reorderLines(order.items, products, lang, { piece: t(lang, "piece"), box: t(lang, "box") });
        const cart = cartId(slug, ctx);
        for (const line of lines) addToCart(cart, { product_id: line.product_id, name: line.name, price_basis: line.price_basis, unit_label: line.unit_label }, line.quantity);
        if (skipped === 0) { window.location.assign(shopHref(slug, lang, "/cart", ctx)); return; }
        setReorderNote(t(lang, lines.length ? "reorderSomeSkipped" : "reorderNoneAvailable"));
        setReordering(false);
      })
      .catch(() => { setReorderNote(t(lang, "reorderFailed")); setReordering(false); });
  };

  if (!order) {
    return state === "missing"
      ? <section className="empty" role="alert"><Icon name="info" /><h2>{t(lang, "orderUnavailableTitle")}</h2><p>{t(lang, "orderUnavailableBody")}</p><p><Link className="text-link" href={shopHref(slug, lang, "", ctx)}>{t(lang, "backToShop")}</Link></p></section>
      : <p className="muted" role="status">{t(lang, "orderLoading")}</p>;
  }
  const statusKey = `orderStatus_${order.status}` as "orderStatus_RECEIVED" | "orderStatus_CONFIRMED" | "orderStatus_DECLINED" | "orderStatus_CANCELLED";
  const received = order.status === "RECEIVED" || order.status === "CONFIRMED";
  return (
    <article className="order" aria-labelledby="order-title">
      {received ? <><span className="success-mark" aria-hidden="true"><Icon name="check" /></span><p className="eyebrow">{t(lang, "orderReceived")}</p></> : null}
      <h2 id="order-title">{t(lang, "orderTitle")}</h2>
      <p className={`notice${order.status === "CONFIRMED" ? " good" : order.status === "RECEIVED" ? "" : " warn"}`} role="status">{t(lang, statusKey)}</p>
      {order.official_number ? <p><strong>{t(lang, "invoiceNumber")}:</strong> <span dir="ltr">{order.official_number}</span></p> : null}
      <dl className="facts">
        <dt>{t(lang, "name")}</dt><dd>{order.contact_name}</dd>
        <dt>{t(lang, "phone")}</dt><dd dir="ltr">{order.contact_phone}</dd>
        <dt>{t(lang, "address")}</dt><dd>{order.contact_address}</dd>
        {order.notes ? <><dt>{t(lang, "notes")}</dt><dd>{order.notes}</dd></> : null}
        <dt>{t(lang, "deliveryDate")}</dt><dd>{order.delivery_date ? <span dir="ltr">{order.delivery_date}</span> : t(lang, "deliveryNotSet")}</dd>
      </dl>
      <h3>{t(lang, "provisionalSummary")}</h3>
      <table className="order-lines">
        <thead><tr><th>{t(lang, "item")}</th><th>{t(lang, "quantity")}</th><th>{t(lang, "unitPrice")}</th><th>{t(lang, "lineTotal")}</th></tr></thead>
        <tbody>
          {order.items.map((item, index) => (
            <tr key={index}>
              <td>{item.name}</td>
              <td dir="ltr">{Number(item.quantity)} {item.unit === "BOX" ? t(lang, "box") : t(lang, "piece")}</td>
              <td dir="ltr">{money(item.unit_price, order.currency)}</td>
              <td dir="ltr">{money(item.total, order.currency)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot><tr><th colSpan={3}>{t(lang, "total")}</th><th dir="ltr">{money(order.net_sales, order.currency)}</th></tr></tfoot>
      </table>
      {order.delivery_date ? <p className="notice good" role="status"><Icon name="clock" small />{t(lang, "deliveryOn", { date: order.delivery_date })}</p> : null}
      {order.decision_note ? <p className="notice">{order.decision_note}</p> : null}
      {order.cancellation === "PENDING" ? <p className="notice warn" ref={pendingNotice} role="status" tabIndex={-1}>{t(lang, "cancelPending")}</p> : null}
      {order.cancellation === "REJECTED" ? <p className="muted">{t(lang, "cancelRejected")}</p> : null}
      {received && order.cancellation !== "PENDING" ? (
        <div className="cancel-form">
          <label htmlFor={reasonId}>{t(lang, "cancelReason")}<input id={reasonId} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <button className="link-button" disabled={asking} onClick={requestCancellation} ref={requestButton} type="button">{t(lang, "requestCancel")}</button>
          {askResult ? <p className="muted" role="status">{askResult}</p> : null}
          <p className="muted">{t(lang, "cancelNote")}</p>
        </div>
      ) : null}
      <p className="muted">{t(lang, "orderProvisionalNote")}</p>
      {order.items.some((item) => item.product_id) ? (
        <div className="reorder">
          <button className="button" disabled={reordering} onClick={orderAgain} type="button">{t(lang, "orderAgain")}</button>
          {reorderNote ? <p className="muted" role="status">{reorderNote} <Link className="text-link" href={shopHref(slug, lang, "/cart", ctx)}>{t(lang, "reviewCart")}</Link></p> : null}
        </div>
      ) : null}
      <p><Link className="button secondary" href={shopHref(slug, lang, "", ctx)}><Arrow back small />{t(lang, "backToShop")}</Link></p>
    </article>
  );
}
