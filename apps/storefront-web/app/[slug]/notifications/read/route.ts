import { NextResponse } from "next/server";

import { apiBase, isValidSlug } from "@/lib/catalog";
import { CONTEXT_HEADER, isContextRef } from "@/lib/format";
import { capabilityFor, personalHeaders } from "@/lib/personal";

/**
 * Marks the customer's notifications as read (D-114).
 * Only the context this tab names is used; without one there is no customer and the answer is 404.
 */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const ref = request.headers.get(CONTEXT_HEADER);
  if (!isValidSlug(slug) || !isContextRef(ref)) return NextResponse.json({ detail: { code: "CUSTOMER_CONTEXT_UNAVAILABLE" } }, { status: 404 });
  const capability = await capabilityFor(slug, ref);
  if (!capability) return NextResponse.json({ detail: { code: "CUSTOMER_CONTEXT_UNAVAILABLE" } }, { status: 404 });
  const upstream = await fetch(`${apiBase()}/api/v1/public/notifications/read`, { method: "POST", headers: await personalHeaders(slug, capability), cache: "no-store" });
  const text = upstream.status === 204 ? "" : await upstream.text();
  return new NextResponse(text || null, { status: upstream.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
