import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { isValidSlug } from "@/lib/catalog";
import { CONTEXT_PARAM, isContextRef } from "@/lib/format";
import {
  COOKIE_MAX_AGE_SECONDS,
  contextCookieName,
  contextRef,
  contextSessionCookieName,
  cookieName,
  isCapability,
  resolveState,
  sessionCookieName,
} from "@/lib/personal";

/**
 * Exchanges the capability from the URL fragment for first-party HttpOnly cookies (D-075).
 * The secret is validated against the API first, so a dead link never leaves a cookie behind.
 * The link gets its own cookie named after its context reference (returned as `ref` for the tab to
 * carry), and the shop-wide cookie remembers it as the most recent link (D-090).
 * DELETE clears one context (`?c=`) — the "exit personalized prices" action — never another one.
 */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isValidSlug(slug)) return NextResponse.json({ ok: false }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { capability?: unknown };
  const capability = typeof body.capability === "string" ? body.capability : "";
  if (!isCapability(capability)) return NextResponse.json({ ok: false, code: "CUSTOMER_LINK_UNAVAILABLE" }, { status: 404 });
  const context = await resolveState(capability);
  if (!context || context.tenant_slug !== slug) {
    return NextResponse.json({ ok: false, code: "CUSTOMER_LINK_UNAVAILABLE" }, { status: 404 });
  }
  const ref = contextRef(capability);
  const response = NextResponse.json({ ok: true, ref, display_name: context.display_name, verification_required: !context.granted }, { headers: { "Cache-Control": "no-store" } });
  for (const name of [contextCookieName(slug, ref), cookieName(slug)]) {
    response.cookies.set({
      name,
      value: capability,
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: `/${slug}`,
      maxAge: COOKIE_MAX_AGE_SECONDS,
    });
  }
  return response;
}

export async function DELETE(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  const clear = (name: string) => response.cookies.set({ name, value: "", httpOnly: true, sameSite: "lax", path: `/${slug}`, maxAge: 0 });
  const ref = new URL(request.url).searchParams.get(CONTEXT_PARAM);
  if (!isContextRef(ref)) {
    clear(cookieName(slug));
    clear(sessionCookieName(slug));
    return response;
  }
  clear(contextCookieName(slug, ref));
  clear(contextSessionCookieName(slug, ref));
  // The shop-wide cookie goes too only when it holds this same link.
  const latest = (await cookies()).get(cookieName(slug))?.value;
  if (isCapability(latest) && contextRef(latest) === ref) {
    clear(cookieName(slug));
    clear(sessionCookieName(slug));
  }
  return response;
}
