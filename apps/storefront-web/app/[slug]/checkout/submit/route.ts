import { NextResponse } from "next/server";

import { apiBase, isValidSlug } from "@/lib/catalog";
import { capabilityFor, personalHeaders } from "@/lib/personal";

/**
 * Forwards the checkout to the API from the server so the HttpOnly personalized cookie (if any)
 * becomes the capability header. The browser's Idempotency-Key is passed through unchanged, so a
 * retry after a lost response returns the same order (PHASE_05.md E).
 */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isValidSlug(slug)) return NextResponse.json({ detail: { code: "STOREFRONT_NOT_FOUND" } }, { status: 404 });
  const key = request.headers.get("Idempotency-Key") ?? "";
  if (!/^[0-9a-f-]{36}$/i.test(key)) return NextResponse.json({ detail: { code: "IDEMPOTENCY_KEY_REQUIRED" } }, { status: 422 });
  const body = await request.text();
  const capability = await capabilityFor(slug);
  const headers: Record<string, string> = { "Content-Type": "application/json", "Idempotency-Key": key, ...(await personalHeaders(slug, capability)) };
  const upstream = await fetch(`${apiBase()}/api/v1/public/${encodeURIComponent(slug)}/checkout`, { method: "POST", headers, body, cache: "no-store" });
  const text = await upstream.text();
  return new NextResponse(text, { status: upstream.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
