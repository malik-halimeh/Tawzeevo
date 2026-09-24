"use client";

import { useState } from "react";

import { CONTEXT_PARAM, isContextRef, shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";

/** Shown while a personalized link is active: who the prices are for and a way out — or, while
 * the business asks for verification, the offer to verify (no prices are personalized yet). */
export function PersonalBanner({ slug, lang, displayName, granted = true, ctx = null }: { slug: string; lang: Lang; displayName: string; granted?: boolean; ctx?: string | null }) {
  const [busy, setBusy] = useState(false);
  const exit = () => {
    setBusy(true);
    // Ends this tab's context only; the page reloads on the same address, which is now public.
    fetch(`/${slug}/access/session${isContextRef(ctx) ? `?${CONTEXT_PARAM}=${ctx}` : ""}`, { method: "DELETE" })
      .catch(() => undefined)
      .finally(() => { window.location.reload(); });
  };
  if (!granted) {
    return (
      <div className="notice personal" role="status">
        <span>{t(lang, "verifyOffer", { name: displayName })}</span>
        <span className="notice-actions">
          <a className="link-button" href={shopHref(slug, lang, "/verify", ctx)}>{t(lang, "verifyLink")}</a>
          <button className="link-button" disabled={busy} onClick={exit} type="button">{t(lang, "personalExit")}</button>
        </span>
      </div>
    );
  }
  return (
    <div className="notice personal" role="status">
      <span>{t(lang, "personalPrices", { name: displayName })}</span>
      <button className="link-button" disabled={busy} onClick={exit} type="button">{t(lang, "personalExit")}</button>
    </div>
  );
}
