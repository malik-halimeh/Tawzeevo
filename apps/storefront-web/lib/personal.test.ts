import { describe, expect, test } from "vitest";

import { isContextRef } from "./format";
import { COOKIE_MAX_AGE_SECONDS, contextCookieName, contextRef, contextSessionCookieName, cookieName, isCapability } from "./personal";

describe("personalized context helpers", () => {
  test("accepts only the opaque capability shape and scopes the cookie per shop", () => {
    const good = `${"a".repeat(32)}.${"b".repeat(43)}`;
    expect(isCapability(good)).toBe(true);
    expect(isCapability(good + "x")).toBe(false);
    expect(isCapability("customer_id=123")).toBe(false);
    expect(isCapability(undefined)).toBe(false);
    expect(cookieName("cedar-van")).toBe("tz_customer_cedar-van");
    expect(COOKIE_MAX_AGE_SECONDS).toBe(30 * 24 * 60 * 60); // 30-day maximum (D-075)
  });

  test("each link gets a stable one-way context reference and its own cookies (D-090)", () => {
    const linkA = `${"a".repeat(32)}.${"A".repeat(43)}`;
    const linkB = `${"a".repeat(32)}.${"B".repeat(43)}`;
    const refA = contextRef(linkA);
    expect(isContextRef(refA)).toBe(true);
    expect(contextRef(linkA)).toBe(refA); // the same link always pins the same context
    expect(contextRef(linkB)).not.toBe(refA);
    expect(refA).not.toContain("A".repeat(8)); // never the secret itself
    expect(contextCookieName("cedar-van", refA)).toBe(`tz_customer_cedar-van_${refA}`);
    expect(contextSessionCookieName("cedar-van", refA)).toBe(`tz_session_cedar-van_${refA}`);
  });
});
