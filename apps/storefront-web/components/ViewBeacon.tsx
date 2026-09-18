"use client";

import { useEffect } from "react";

/**
 * Pseudonymous view signal (PHASE_05.md D; D-062). The session id is a random value kept in this
 * browser only; the server stores a hash of it and counts one view per product per 30 minutes.
 * Nothing about the visitor is sent.
 */
const SESSION_KEY = "tawzeevo.storefront.session";

function sessionId(): string | null {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, created);
    return created;
  } catch {
    return null;
  }
}

export function ViewBeacon({ slug, productId }: { slug: string; productId: string }) {
  useEffect(() => {
    const session = sessionId();
    if (!session) return;
    const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
    void fetch(`${base}/api/v1/public/${encodeURIComponent(slug)}/catalog/products/${encodeURIComponent(productId)}/view`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: session }),
      keepalive: true,
    }).catch(() => undefined);
  }, [slug, productId]);
  return null;
}
