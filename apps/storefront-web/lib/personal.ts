import { createHash } from "node:crypto";

import { cookies } from "next/headers";

import { apiBase } from "./catalog";
import { isContextRef } from "./format";

/**
 * Personalized customer context on the storefront (D-071, D-072, D-075, D-090). The opaque
 * capability lives only in first-party HttpOnly cookies scoped to this shop; every request
 * re-resolves it on the API, so rotation/revocation/suspension end the context at once. The cookies
 * never hold customer data.
 *
 * Each opened link gets its own cookie, named after its context reference (a one-way digest, see
 * `contextRef`), and a tab carries that reference in `?c=`. So two customers' storefronts can be
 * open in two tabs of one browser without either tab changing the other's customer, cart or
 * checkout. The shop-wide cookie keeps the most recently opened link for a bare address.
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
  /** Granted contexts only: whether an address is on file (never the address itself; D-090). */
  has_saved_address?: boolean;
}

export function cookieName(slug: string): string {
  return `tz_customer_${slug}`;
}

/** The verified-session secret (P9-M5) lives in a second first-party HttpOnly cookie. */
export function sessionCookieName(slug: string): string {
  return `tz_session_${slug}`;
}

/** A tab's context reference: a one-way digest of the capability, never the capability or its
 * stored hash (the API keeps a plain SHA-256; this one is domain-separated and truncated). */
export function contextRef(capability: string): string {
  return createHash("sha256").update(`tawzeevo-ctx:${capability}`).digest("hex").slice(0, 24);
}

export function contextCookieName(slug: string, ref: string): string {
  return `${cookieName(slug)}_${ref}`;
}

export function contextSessionCookieName(slug: string, ref: string): string {
  return `${sessionCookieName(slug)}_${ref}`;
}

export function isCapability(value: string | undefined | null): value is string {
  return Boolean(value && TOKEN.test(value));
}

async function jarValue(name: string): Promise<string | null> {
  try {
    const value = (await cookies()).get(name)?.value;
    return isCapability(value) ? value : null;
  } catch {
    return null;
  }
}

/**
 * The capability for one tab. With a context reference only that context's link is used (or the
 * shop-wide cookie when it is that same link, e.g. set before per-context cookies existed); an
 * unknown reference is the public storefront, never another customer. Without a reference (a bare
 * address) the most recently opened link applies, as before.
 */
export async function capabilityFor(slug: string, ref?: string | null): Promise<string | null> {
  const latest = await jarValue(cookieName(slug));
  if (ref === undefined || ref === null) return latest;
  if (!isContextRef(ref)) return null;
  const pinned = await jarValue(contextCookieName(slug, ref));
  if (pinned) return pinned;
  return latest && contextRef(latest) === ref ? latest : null;
}

export async function sessionFor(slug: string, ref?: string | null): Promise<string | null> {
  const pinned = isContextRef(ref) ? await jarValue(contextSessionCookieName(slug, ref)) : null;
  return pinned ?? (await jarValue(sessionCookieName(slug)));
}

/** Headers that carry the visitor's secrets to the API (capability, and the session when any).
 * The API accepts a session only for the link it was issued to, so a mismatch is harmless. */
export async function personalHeaders(slug: string, capability: string | null): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (!capability) return headers;
  headers[CAPABILITY_HEADER] = capability;
  const session = await sessionFor(slug, contextRef(capability));
  if (session) headers[SESSION_HEADER] = session;
  return headers;
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

/** Everything a page needs in one call: the full state (for the banner/verification offer), the
 * personal payload to send with catalog requests (null while nothing is granted), and the context
 * reference every link on the page must carry (`ctx`; the requested one when it did not resolve,
 * so the tab stays pinned to that context instead of picking up another customer's link). */
export async function visitorFor(slug: string, requested?: string | null): Promise<{ state: CustomerContext | null; personal: { capability: string; session: string | null } | null; ctx: string | null }> {
  const pinned = isContextRef(requested) ? requested : null;
  const capability = await capabilityFor(slug, requested ?? null);
  if (!capability) return { state: null, personal: null, ctx: pinned };
  const ref = contextRef(capability);
  const session = await sessionFor(slug, ref);
  const state = await resolveState(capability, session);
  return { state, personal: state?.granted ? { capability, session } : null, ctx: state ? ref : pinned };
}
