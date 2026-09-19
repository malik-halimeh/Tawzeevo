import type { CSSProperties } from "react";

/**
 * Business colours become CSS tokens only when they stay readable (PHASE_08.md H: accessibility
 * is mandatory; colour never carries meaning alone). A primary colour is used for text and
 * buttons only when it reaches WCAG AA contrast (4.5:1) against the white paper; the ink on any
 * accent background is chosen black or white from the colour's luminance. Layout stays ours.
 */
const HEX = /^#([0-9a-f]{6})$/i;
const AA_TEXT = 4.5;

function luminance(hex: string): number {
  const channel = (index: number) => {
    const value = parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(0) + 0.7152 * channel(1) + 0.0722 * channel(2);
}

export function contrastRatio(hexA: string, hexB: string): number {
  const [light, dark] = [luminance(hexA), luminance(hexB)].sort((a, b) => b - a) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

export function inkFor(hex: string): "#000000" | "#ffffff" {
  return contrastRatio(hex, "#000000") >= contrastRatio(hex, "#ffffff") ? "#000000" : "#ffffff";
}

export function themeTokens(primary: string | null | undefined, secondary: string | null | undefined): CSSProperties | undefined {
  const tokens: Record<string, string> = {};
  if (primary && HEX.test(primary) && contrastRatio(primary, "#ffffff") >= AA_TEXT) {
    tokens["--accent"] = primary.toLowerCase();
    tokens["--accent-ink"] = inkFor(primary);
  }
  if (secondary && HEX.test(secondary)) {
    tokens["--accent-soft"] = secondary.toLowerCase();
    tokens["--accent-soft-ink"] = inkFor(secondary);
  }
  return Object.keys(tokens).length ? (tokens as CSSProperties) : undefined;
}
