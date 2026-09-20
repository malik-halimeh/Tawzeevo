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
export const SESSION_HEADER = "X-Customer-Session";
const TOKEN = /^[a-f0-9]{32}\.[A-Za-z0-9_-]{43}$/;

/** Full visitor state as the API reports it; `granted` is false while verification is required. */
export interface CustomerContext {
  assurance: "LINK" | "VERIFIED";
  tenant_slug: string;
  display_name: string;
  required_policy: "LINK" | "VERIFIED" | "ACCOUNT_REQUIRED";
  granted: boolean;
  contact_hint: string;
}

export function cookieName(slug: string): string {
  return `tz_customer_${slug}`;
}

/** The verified-session secret (P9-M5) lives in a second first-party HttpOnly cookie. */
export function sessionCookieName(slug: string): string {
  return `tz_session_${slug}`;
}

export async function sessionFor(slug: string): Promise<string | null> {
  try {
    const value = (await cookies()).get(sessionCookieName(slug))?.value;
    return isCapability(value) ? value : null;
  } catch {
    return null;
  }
}

/** Headers that carry the visitor's secrets to the API (capability, and the session when any). */
export async function personalHeaders(slug: string, capability: string | null): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (!capability) return headers;
  headers[CAPABILITY_HEADER] = capability;
  const session = await sessionFor(slug);
  if (session) headers[SESSION_HEADER] = session;
  return headers;
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

/** Ask the API what this visitor holds; any failure means anonymous. */
export async function resolveState(capability: string | null, session: string | null = null): Promise<CustomerContext | null> {
  if (!capability) return null;
  try {
    const headers: Record<string, string> = { [CAPABILITY_HEADER]: capability };
    if (session) headers[SESSION_HEADER] = session;
    const response = await fetch(`${apiBase()}/api/v1/public/customer-context`, { headers, cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as CustomerContext;
  } catch {
    return null;
  }
}

/** The granted context only: personalized prices and checkout see a customer solely when the
 * held assurance satisfies the policy (D-072). Pages that must offer verification use resolveState. */
export async function resolveContext(capability: string | null, session: string | null = null): Promise<CustomerContext | null> {
  const state = await resolveState(capability, session);
  return state?.granted ? state : null;
}

/** Everything a page needs in one call: the full state (for the banner/verification offer) and
 * the personal payload to send with catalog requests (null while nothing is granted). */
export async function visitorFor(slug: string): Promise<{ state: CustomerContext | null; personal: { capability: string; session: string | null } | null }> {
  const capability = await capabilityFor(slug);
  if (!capability) return { state: null, personal: null };
  const session = await sessionFor(slug);
  const state = await resolveState(capability, session);
  return { state, personal: state?.granted ? { capability, session } : null };
}
