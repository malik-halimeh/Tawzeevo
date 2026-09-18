import { describe, expect, test } from "vitest";

import { COOKIE_MAX_AGE_SECONDS, cookieName, isCapability } from "./personal";

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
});
