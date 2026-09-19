import { describe, expect, it } from "vitest";

import { contrastRatio, inkFor, themeTokens } from "./theme";

describe("branding theme tokens stay readable", () => {
  it("uses a dark primary colour for text and picks white ink on it", () => {
    expect(themeTokens("#1F6F5F", null)).toEqual({ "--accent": "#1f6f5f", "--accent-ink": "#ffffff" });
  });
  it("refuses a light primary colour as text (below 4.5:1 on white) but keeps a secondary with black ink", () => {
    expect(contrastRatio("#f2c14e", "#ffffff")).toBeLessThan(4.5);
    expect(themeTokens("#f2c14e", "#f2c14e")).toEqual({ "--accent-soft": "#f2c14e", "--accent-soft-ink": "#000000" });
  });
  it("ignores anything that is not #rrggbb and returns nothing when no token applies", () => {
    expect(themeTokens("red", "url(x)")).toBeUndefined();
    expect(themeTokens(null, undefined)).toBeUndefined();
  });
  it("chooses ink by contrast", () => {
    expect(inkFor("#000000")).toBe("#ffffff");
    expect(inkFor("#ffffff")).toBe("#000000");
  });
});
