"use client";

import { useEffect, useState } from "react";

import { shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";
import { Icon } from "./Icon";

/**
 * Reads the capability from the URL fragment (never sent to any server by the browser), posts it
 * to the shop's session route, removes the fragment from the address bar, and continues to the
 * shop. A dead or foreign link shows a plain message and no cookie is set.
 */
export function AccessEntry({ slug, lang }: { slug: string; lang: Lang }) {
  const [state, setState] = useState<"working" | "failed">("working");

  useEffect(() => {
    const secret = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
    if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
    const exchange = async () => {
      if (!secret) return false;
      const response = await fetch(`/${slug}/access/session`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ capability: secret }) });
      if (!response.ok) return false;
      const body = (await response.json().catch(() => ({}))) as { verification_required?: boolean; ref?: string };
      return { verify: Boolean(body.verification_required), ref: body.ref ?? null };
    };
    exchange()
      .then((result) => {
        if (!result) setState("failed");
        else window.location.replace(shopHref(slug, lang, result.verify ? "/verify" : "", result.ref));
      })
      .catch(() => setState("failed"));
  }, [slug, lang]);

  if (state === "failed") {
    return (
      <section className="empty" role="alert">
        <Icon name="info" />
        <h2>{t(lang, "linkUnavailableTitle")}</h2>
        <p>{t(lang, "linkUnavailableBody")}</p>
        <p><a className="text-link" href={shopHref(slug, lang)}>{t(lang, "backToShop")}</a></p>
      </section>
    );
  }
  return <p className="muted" role="status">{t(lang, "linkOpening")}</p>;
}
