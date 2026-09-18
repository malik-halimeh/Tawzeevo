import { NextResponse } from "next/server";

import { apiBase, isValidSlug } from "@/lib/catalog";

/** Proxies a customer's cancellation *request*; the owner decides (PHASE_05.md J). */
export async function POST(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!isValidSlug(slug)) return NextResponse.json({ detail: { code: "STOREFRONT_NOT_FOUND" } }, { status: 404 });
  const body = (await request.json().catch(() => ({}))) as { reference?: unknown; reason?: unknown };
  const reference = typeof body.reference === "string" ? body.reference : "";
  if (!/^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/.test(reference)) return NextResponse.json({ detail: { code: "ORDER_REFERENCE_UNAVAILABLE" } }, { status: 404 });
  const reason = typeof body.reason === "string" ? body.reason.slice(0, 500) : null;
  const upstream = await fetch(`${apiBase()}/api/v1/public/order/cancellation-request`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Order-Reference": reference },
    body: JSON.stringify({ reason }),
    cache: "no-store",
  });
  const text = await upstream.text();
  return new NextResponse(text, { status: upstream.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
