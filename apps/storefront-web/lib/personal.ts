import { cookies } from "next/headers";

import { apiBase } from "./catalog";

/**
 * Personalized customer context on the storefront (D-071, D-072, D-075). The opaque capability
 * lives only in a first-party HttpOnly cookie scoped to this shop; every request re-resolves it
 * on the API, so rotation/revocation/suspension end the context at once. The cookie never holds
 * customer data, and a valid context means assurance LINK — nothing more.
 */
export const COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60; // 30-day maximum (D-075)
export const CAPABILITY_HEADER = "X-Customer-Capability";
const TOKEN = /^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/;

export interface CustomerContext {
  assurance: "LINK";
  tenant_slug: string;
  display_name: string;
}

export function cookieName(slug: string): string {
  return `tz_customer_${slug}`;
}

export function isCapability(value: string | undefined | null): value is string {
  return Boolean(value && TOKEN.test(value));
}

export async function capabilityFor(slug: string): Promise<string | null> {
  try {
    const value = (await cookies()).get(cookieName(slug))?.value;
    return isCapability(value) ? value : null;
  } catch {
    return null;
  }
}

/** Ask the API who this capability is for; any failure means anonymous. */
export async function resolveContext(capability: string | null): Promise<CustomerContext | null> {
  if (!capability) return null;
  try {
    const response = await fetch(`${apiBase()}/api/v1/public/customer-context`, {
      headers: { [CAPABILITY_HEADER]: capability },
      cache: "no-store",
    });
    if (!response.ok) return null;
    const body = (await response.json()) as CustomerContext;
    return body.assurance === "LINK" ? body : null;
  } catch {
    return null;
  }
}
