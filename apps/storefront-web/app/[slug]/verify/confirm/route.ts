import { NextResponse } from "next/server";

import { apiBase, isValidSlug } from "@/lib/catalog";
import { CAPABILITY_HEADER, COOKIE_MAX_AGE_SECONDS, capabilityFor, sessionCookieName } from "@/lib/personal";

/** Trades the code for the verified session; the secret goes into an HttpOnly cookie only. */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isValidSlug(slug)) return NextResponse.json({ ok: false }, { status: 404 });
  const capability = await capabilityFor(slug);
  if (!capability) return NextResponse.json({ ok: false, code: "CUSTOMER_LINK_UNAVAILABLE" }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { code?: unknown };
  const code = typeof body.code === "string" ? body.code.trim() : "";
  const upstream = await fetch(`${apiBase()}/api/v1/public/customer-verification/confirm`, {
    method: "POST",
    headers: { [CAPABILITY_HEADER]: capability, "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
    cache: "no-store",
  });
  const payload = (await upstream.json().catch(() => ({}))) as { session?: string; expires_at?: string; detail?: { code?: string } };
  if (!upstream.ok || !payload.session) {
    return NextResponse.json({ ok: false, code: payload.detail?.code ?? "VERIFICATION_CODE_INVALID" }, { status: upstream.ok ? 400 : upstream.status, headers: { "Cache-Control": "no-store" } });
  }
  const expires = payload.expires_at ? Math.max(60, Math.floor((new Date(payload.expires_at).getTime() - Date.now()) / 1000)) : COOKIE_MAX_AGE_SECONDS;
  const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.set({
    name: sessionCookieName(slug),
    value: payload.session,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: `/${slug}`,
    maxAge: Math.min(expires, COOKIE_MAX_AGE_SECONDS),
  });
  return response;
}
