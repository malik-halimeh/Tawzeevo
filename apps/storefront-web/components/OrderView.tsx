"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { money, shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";
import { Arrow, Icon } from "./Icon";

interface ProvisionalItem { name: string; quantity: string; unit: string; pieces_per_box: number | null; unit_price: string; total: string }
interface ProvisionalOrder {
  business_name: string; status: string; contact_name: string; contact_phone: string; contact_address: string; notes: string | null;
  currency: string; created_at: string; invoice_status: string | null; official_number: string | null;
  subtotal: string; discount: string; markup: string; net_sales: string; items: ProvisionalItem[]; decision_note: string | null;
  delivery_date: string | null; cancellation: "PENDING" | "APPROVED" | "REJECTED" | null;
}

const KEY = (slug: string) => `tawzeevo.order-ref.${slug}`;

/**
 * Provisional order page (D-046): the reference arrives in the URL fragment, is kept in this
 * browser's sessionStorage for revisits within its lifetime, and is sent only in a private
 * header through the shop's proxy. It shows the order as submitted — not a confirmed invoice.
 */
export function OrderView({ slug, lang }: { slug: string; lang: Lang }) {
  const [order, setOrder] = useState<ProvisionalOrder>();
  const [state, setState] = useState<"loading" | "missing">("loading");
  const referenceRef = useRef("");
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const [askResult, setAskResult] = useState<string>();
  const reasonId = useId();

  const requestCancellation = () => {
    const reference = referenceRef.current;
    if (!reference) return;
    setAsking(true);
    fetch(`/${slug}/order/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reference, reason: reason.trim() || null }) })
      .then(async (response) => {
        if (!response.ok) { setAskResult(t(lang, "cancelFailed")); return; }
        setAskResult(t(lang, "cancelRequested"));
        setOrder((current) => (current ? { ...current, cancellation: "PENDING" } : current));
      })
      .catch(() => setAskResult(t(lang, "cancelFailed")))
      .finally(() => setAsking(false));
  };

  useEffect(() => {
    let reference = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
    if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
    try {
      if (reference) sessionStorage.setItem(KEY(slug), reference);
      else reference = sessionStorage.getItem(KEY(slug)) ?? "";
    } catch { /* no storage: the fragment alone must do */ }
    referenceRef.current = reference;
    const load = async () => {
      if (!reference) return null;
      const response = await fetch(`/${slug}/order/view`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reference }) });
      return response.ok ? ((await response.json()) as ProvisionalOrder) : null;
    };
    load().then((result) => { if (result) setOrder(result); else setState("missing"); }).catch(() => setState("missing"));
  }, [slug]);

  if (!order) {
    return state === "missing"
      ? <section className="empty" role="alert"><Icon name="info" /><h2>{t(lang, "orderUnavailableTitle")}</h2><p>{t(lang, "orderUnavailableBody")}</p><p><Link className="text-link" href={shopHref(slug, lang)}>{t(lang, "backToShop")}</Link></p></section>
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
      {order.cancellation === "PENDING" ? <p className="notice warn" role="status">{t(lang, "cancelPending")}</p> : null}
      {order.cancellation === "REJECTED" ? <p className="muted">{t(lang, "cancelRejected")}</p> : null}
      {received && order.cancellation !== "PENDING" ? (
        <div className="cancel-form">
          <label htmlFor={reasonId}>{t(lang, "cancelReason")}<input id={reasonId} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <button className="link-button" disabled={asking} onClick={requestCancellation} type="button">{t(lang, "requestCancel")}</button>
          {askResult ? <p className="muted" role="status">{askResult}</p> : null}
          <p className="muted">{t(lang, "cancelNote")}</p>
        </div>
      ) : null}
      <p className="muted">{t(lang, "orderProvisionalNote")}</p>
      <p><Link className="button secondary" href={shopHref(slug, lang)}><Arrow back small />{t(lang, "backToShop")}</Link></p>
    </article>
  );
}
