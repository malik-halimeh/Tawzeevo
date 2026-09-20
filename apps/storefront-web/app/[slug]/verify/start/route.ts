import { NextResponse } from "next/server";

import { apiBase, isValidSlug } from "@/lib/catalog";
import { CAPABILITY_HEADER, capabilityFor } from "@/lib/personal";

/** Asks the API to send a one-time code to the customer's own phone (P9-M5). */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isValidSlug(slug)) return NextResponse.json({ ok: false }, { status: 404 });
  const capability = await capabilityFor(slug);
  if (!capability) return NextResponse.json({ ok: false, code: "CUSTOMER_LINK_UNAVAILABLE" }, { status: 404 });
  const upstream = await fetch(`${apiBase()}/api/v1/public/customer-verification/start`, {
    method: "POST",
    headers: { [CAPABILITY_HEADER]: capability, "Accept-Language": request.headers.get("accept-language") ?? "en" },
    cache: "no-store",
  });
  const body = (await upstream.json().catch(() => ({}))) as { detail?: { code?: string } };
  return NextResponse.json({ ok: upstream.ok, code: body.detail?.code ?? null }, { status: upstream.ok ? 200 : upstream.status, headers: { "Cache-Control": "no-store" } });
}
