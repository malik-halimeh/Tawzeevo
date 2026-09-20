import { NextResponse } from "next/server";

import { isValidSlug } from "@/lib/catalog";
import { COOKIE_MAX_AGE_SECONDS, cookieName, isCapability, resolveState, sessionCookieName } from "@/lib/personal";

/**
 * Exchanges the capability from the URL fragment for a first-party HttpOnly cookie (D-075).
 * The secret is validated against the API first, so a dead link never leaves a cookie behind.
 * DELETE clears the cookie (the "exit personalized prices" action).
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
  const response = NextResponse.json({ ok: true, display_name: context.display_name, verification_required: !context.granted }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.set({
    name: cookieName(slug),
    value: capability,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: `/${slug}`,
    maxAge: COOKIE_MAX_AGE_SECONDS,
  });
  return response;
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.set({ name: cookieName(slug), value: "", httpOnly: true, sameSite: "lax", path: `/${slug}`, maxAge: 0 });
  response.cookies.set({ name: sessionCookieName(slug), value: "", httpOnly: true, sameSite: "lax", path: `/${slug}`, maxAge: 0 });
  return response;
}
