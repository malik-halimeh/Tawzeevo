"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { CONTEXT_HEADER, shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";
import { type CustomerNotification, notificationText } from "@/lib/notifications";

/**
 * The customer's notifications on their personalized storefront (D-114): payments the shop recorded.
 * Reached only through the tab's own link context; a public visitor has none.
 */
interface NotificationList { unread: number; notifications: CustomerNotification[] }
const EVENT = "tawzeevo:notifications";

function load(slug: string, ctx: string): Promise<NotificationList | null> {
  return fetch(`/${slug}/notifications/list`, { method: "POST", headers: { [CONTEXT_HEADER]: ctx } })
    .then(async (response) => (response.ok ? ((await response.json()) as NotificationList) : null))
    .catch(() => null);
}

/** Header link with the unread count, for a personalized tab only. */
export function NotificationsLink({ slug, lang, ctx }: { slug: string; lang: Lang; ctx: string }) {
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    let live = true;
    const refresh = () => { void load(slug, ctx).then((body) => { if (live && body) setUnread(body.unread); }); };
    const id = window.setTimeout(refresh, 0);
    window.addEventListener(EVENT, refresh);
    return () => { live = false; window.clearTimeout(id); window.removeEventListener(EVENT, refresh); };
  }, [slug, ctx]);
  return (
    <Link className="order-link" href={shopHref(slug, lang, "/notifications", ctx)}>
      {t(lang, "notifications")}{unread > 0 ? <span className="cart-count" aria-label={t(lang, "notificationsUnread", { count: unread })}>{unread}</span> : null}
    </Link>
  );
}

export function NotificationsView({ slug, lang, ctx }: { slug: string; lang: Lang; ctx: string | null }) {
  const [list, setList] = useState<NotificationList | null>();
  useEffect(() => {
    if (!ctx) { const id = window.setTimeout(() => setList(null), 0); return () => window.clearTimeout(id); }
    let live = true;
    void load(slug, ctx).then((body) => {
      if (!live) return;
      setList(body);
      // Seen now: mark them read, then let the header count follow.
      if (body && body.unread > 0) {
        void fetch(`/${slug}/notifications/read`, { method: "POST", headers: { [CONTEXT_HEADER]: ctx } })
          .then(() => window.dispatchEvent(new CustomEvent(EVENT)))
          .catch(() => undefined);
      }
    });
    return () => { live = false; };
  }, [slug, ctx]);
  if (list === undefined) return <p className="muted" role="status">{t(lang, "orderLoading")}</p>;
  if (list === null) return <p className="notice" role="status">{t(lang, "notificationsUnavailable")} <Link className="text-link" href={shopHref(slug, lang, "", ctx)}>{t(lang, "backToShop")}</Link></p>;
  if (!list.notifications.length) return <p className="muted">{t(lang, "notificationsEmpty")}</p>;
  return (
    <ul className="notification-list" aria-label={t(lang, "notifications")}>
      {list.notifications.map((item) => (
        <li className={item.read ? "" : "unread"} key={item.id}>
          <p>{notificationText(lang, item)}</p>
          <time className="muted" dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(lang === "ar" ? "ar-LB" : "en-GB")}</time>
        </li>
      ))}
    </ul>
  );
}
