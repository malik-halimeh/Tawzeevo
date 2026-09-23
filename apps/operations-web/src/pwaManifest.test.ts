/**
 * Installability of the operations PWA (D-004; audit finding TWZ-F-011): the manifest must
 * declare 192 px and 512 px PNG icons that really exist with those dimensions, plus the
 * members Chromium requires for an install prompt.
 */
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const publicDir = resolve(__dirname, "..", "public");
const manifest = JSON.parse(readFileSync(resolve(publicDir, "manifest.webmanifest"), "utf8")) as {
  name: string;
  short_name: string;
  start_url: string;
  display: string;
  theme_color: string;
  background_color: string;
  icons: { src: string; sizes: string; type: string; purpose?: string }[];
};

function pngDimensions(bytes: Buffer): { width: number; height: number } {
  // PNG signature, then the IHDR chunk: width and height are the first two big-endian uint32s.
  expect(bytes.subarray(0, 8)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  expect(bytes.subarray(12, 16).toString("ascii")).toBe("IHDR");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

describe("PWA manifest", () => {
  it("carries the installability members", () => {
    expect(manifest.name).toBe("Tawzeevo Operations");
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBe("/");
    expect(["standalone", "fullscreen", "minimal-ui"]).toContain(manifest.display);
    expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/i);
    expect(manifest.background_color).toMatch(/^#[0-9a-f]{6}$/i);
    // The theme colour is the one index.html already declares (design token --ink).
    const html = readFileSync(resolve(__dirname, "..", "index.html"), "utf8");
    expect(html).toContain(`<meta name="theme-color" content="${manifest.theme_color}" />`);
    expect(html).toContain('<link rel="manifest" href="/manifest.webmanifest" />');
  });

  it("declares 192 and 512 px PNG icons that exist with those dimensions (any + maskable)", () => {
    const declared = new Map(manifest.icons.map((icon) => [`${icon.sizes}:${icon.purpose ?? "any"}`, icon]));
    for (const key of ["192x192:any", "512x512:any", "192x192:maskable", "512x512:maskable"]) {
      expect(declared.has(key), `manifest lacks icon ${key}`).toBe(true);
    }
    for (const icon of manifest.icons) {
      expect(icon.type).toBe("image/png");
      expect(icon.src.startsWith("/")).toBe(true);
      const [width, height] = icon.sizes.split("x").map(Number);
      const bytes = readFileSync(resolve(publicDir, icon.src.slice(1)));
      expect(pngDimensions(bytes)).toEqual({ width, height });
    }
  });
});
