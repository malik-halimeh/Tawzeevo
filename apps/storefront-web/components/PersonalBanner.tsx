"use client";

import { useState } from "react";

import { type Lang, t } from "@/lib/i18n";

/** Shown while a personalized context is active: who the prices are for, and a way out. */
export function PersonalBanner({ slug, lang, displayName }: { slug: string; lang: Lang; displayName: string }) {
  const [busy, setBusy] = useState(false);
  const exit = () => {
    setBusy(true);
    fetch(`/${slug}/access/session`, { method: "DELETE" })
      .catch(() => undefined)
      .finally(() => { window.location.reload(); });
  };
  return (
    <div className="notice personal" role="status">
      <span>{t(lang, "personalPrices", { name: displayName })}</span>{" "}
      <button className="link-button" disabled={busy} onClick={exit} type="button">{t(lang, "personalExit")}</button>
    </div>
  );
}
