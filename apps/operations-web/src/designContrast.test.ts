/// <reference types="node" />
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import postcss, { type AnyNode } from "postcss";
import { describe, expect, it } from "vitest";

const sheets = ["styles.css", "map.css"].map((file) => postcss.parse(
  readFileSync(resolve(__dirname, file), "utf8"), { from: file },
));

type Scheme = "light" | "dark";

function applies(node: AnyNode, medium: "screen" | "print", scheme: Scheme = "light"): boolean {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent instanceof postcss.AtRule && parent.name === "media") {
      if (/prefers-color-scheme:\s*dark/.test(parent.params) && scheme !== "dark") return false;
      if (/\bprint\b/.test(parent.params) && medium !== "print") return false;
      if (/\bscreen\b/.test(parent.params) && medium !== "screen") return false;
    }
  }
  return true;
}

function rootTokens(medium: "screen" | "print", scheme: Scheme = "light"): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const sheet of sheets) {
    sheet.walkRules((rule) => {
      if (!rule.selectors.includes(":root") || !applies(rule, medium, scheme)) return;
      rule.walkDecls(({ prop, value }) => { if (prop.startsWith("--")) tokens[prop] = value; });
    });
  }
  return tokens;
}

function tokenValue(tokens: Record<string, string>, value: string, visited: string[] = []): string {
  return value.replace(/var\((--[\w-]+)\)/g, (reference, name: string) => {
    const definition = tokens[name];
    if (definition === undefined) return reference;
    if (visited.includes(name)) throw new Error(`Cyclic token: ${name}`);
    return tokenValue(tokens, definition, [...visited, name]);
  });
}

const light = rootTokens("screen");

function luminance(hex: string): number {
  if (!/^#[\da-f]{3}(?:[\da-f]{3})?$/i.test(hex)) throw new Error(`Expected opaque hex colour: ${hex}`);
  const digits = hex.length === 4 ? hex.slice(1).split("").map((digit) => digit + digit).join("") : hex.slice(1);
  const linear = (offset: number) => {
    const channel = parseInt(digits.slice(offset, offset + 2), 16) / 255;
    return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
  };
  return linear(0) * 0.2126 + linear(2) * 0.7152 + linear(4) * 0.0722;
}

function contrast(foreground: string, background: string): number {
  const values = [luminance(foreground), luminance(background)];
  return (Math.max(...values) + 0.05) / (Math.min(...values) + 0.05);
}

function stops(tokens: Record<string, string>, name: string): string[] {
  const colours = tokenValue(tokens, `var(${name})`).match(/#[\da-f]{3}(?:[\da-f]{3})?\b/gi);
  if (!colours?.length) throw new Error(`No surface colours: ${name}`);
  return colours;
}

function meets(foreground: string, background: string, target = 4.5): void {
  const ratio = contrast(foreground, background);
  expect(ratio, `${foreground} on ${background}: ${ratio.toFixed(4)}:1, requires ${target}:1`)
    .toBeGreaterThanOrEqual(target);
}

describe.each(["light", "dark"] as const)("%s design contrast", (scheme) => {
  const tokens = rootTokens("screen", scheme);
  const value = (name: string) => tokenValue(tokens, `var(${name})`);
  it("calculates the WCAG black/white reference ratio", () => {
    expect(contrast("#000", "#fff")).toBe(21);
    expect(contrast("#fff", "#000")).toBe(21);
  });

  for (const foreground of ["--ink", "--muted"]) {
    for (const background of ["--bg-solid", "--card-solid", "--field-bg", "--mist", "--chip-solid"]) {
      it(`${foreground} on ${background} reaches 4.5:1`, () => meets(value(foreground), value(background)));
    }
    it(`${foreground} on every bar stop reaches 4.5:1`, () => {
      for (const stop of stops(tokens, "--bar")) meets(value(foreground), stop);
    });
    it(`${foreground} on every page stop reaches 4.5:1`, () => {
      for (const stop of stops(tokens, "--bg")) meets(value(foreground), stop);
    });
  }

  for (const background of ["--bg-solid", "--card-solid"]) {
    it(`links on ${background} reach 4.5:1`, () => meets(value("--blue"), value(background)));
  }
  for (const background of ["--accent", "--accent-hover"]) {
    it(`action text on every ${background} stop reaches 4.5:1`, () => {
      for (const stop of stops(tokens, background)) meets(value("--accent-ink"), stop);
    });
  }
  for (const meaning of ["good", "warn", "bad"]) {
    it(`${meaning} text on its background reaches 4.5:1`, () => meets(value(`--${meaning}`), value(`--${meaning}-bg`)));
  }
  it("strong edges on card solid reach 3:1", () => meets(value("--edge-strong"), value("--card-solid"), 3));
  it("keeps Cedar surfaces flat and fields softly tinted", () => {
    const surfaces = scheme === "dark" ? {
      "--bg": "#0e1714", "--bar": "#121c19", "--card": "#16221e", "--chip": "#16221e",
      "--field-bg": "#1b2925", "--accent": "#2fbf8f", "--accent-hover": "#3ad6a3",
    } : {
      "--bg": "#f3f6f4", "--bar": "#ffffff", "--card": "#ffffff", "--chip": "#ffffff",
      "--field-bg": "#f5f8f6", "--accent": "#0f6b55", "--accent-hover": "#0b5644",
    };
    for (const [name, expected] of Object.entries(surfaces)) expect(value(name), name).toBe(expected);
    for (const name of ["bg", "bar", "card", "chip", "accent"]) {
      expect(value(`--${name}-solid`)).toBe(value(`--${name}`));
    }
  });
  it("solid action text on primary reaches 4.5:1", () => meets(value("--on-solid"), value("--accent")));
  for (const foreground of ["--band-ink", "--band-muted"]) {
    it(`${foreground} on both band stops reaches 4.5:1`, () => {
      for (const stop of stops(tokens, "--band")) meets(value(foreground), stop);
    });
  }
  it("white glass-pill text on both composited band stops reaches 4.5:1", () => {
    const glass = value("--band-glass").match(/^rgb\(255 255 255 \/ ([\d.]+)\)$/);
    expect(glass).not.toBeNull();
    const opacity = Number(glass![1]);
    for (const stop of stops(tokens, "--band")) {
      const background = "#" + stop.slice(1).match(/../g)!.map((channel) =>
        Math.round(255 * opacity + parseInt(channel, 16) * (1 - opacity)).toString(16).padStart(2, "0"),
      ).join("");
      meets(value("--band-ink"), background);
    }
  });
  it("mint ink on mint reaches 4.5:1", () => meets(value("--mint-ink"), value("--citron")));
  for (const foreground of ["--ink", "--muted"]) {
    it(`${foreground} on the field reaches 4.5:1`, () => meets(value(foreground), value("--field-bg")));
  }
  for (const [foreground, background] of [
    ["--nav-ink", "--nav-bg"], ["--nav-tint-ink", "--mist"],
    ["--nav-tint-ink", "--active-tab-bg"], ["--badge-ink", "--badge-bg"],
    ["--on-mint", "--citron"], ["--on-solid", "--solid-bg"],
    ["--accent-ink", "--good"], ["--accent-ink", "--good-hover"],
    ["--lc-deep", "--lc-tint"], ["--lc-on", "--lc"], ["--lc-on", "--lc-deep"],
    ["--desk-title-ink", "--desk-bg"], ["--desk-muted", "--desk-bg"],
    ["--board-ink", "--board-bg"], ["--citron", "--board-bg"],
    ["--sales-art-ink", "--sales-art-bg"], ["--customers-art-ink", "--customers-art-bg"],
    ["--ink", "--closed-tag-bg"], ["--muted", "--closed-tag-bg"],
  ]) {
    it(`${foreground} on ${background} reaches 4.5:1`, () => meets(value(foreground!), value(background!)));
  }
  for (const foreground of ["--sales-art", "--customers-art", "--catalog-art", "--buying-art", "--lc-edge"]) {
    it(`${foreground} artwork/edge on card reaches 3:1`, () => meets(value(foreground), value("--card-solid"), 3));
  }
  for (const name of ["--select-indicator", "--search-indicator"]) {
    it(`${name} stays visible on fields at 3:1`, () => {
      const stroke = decodeURIComponent(value(name)).match(/stroke='(#[\da-f]{6})'/i);
      expect(stroke).not.toBeNull();
      meets(stroke![1]!, value("--field-bg"), 3);
    });
  }
  it("chart bars stay visible against their tint at 3:1", () => meets(value("--blue"), value("--mist"), 3));
  if (scheme === "dark") {
    for (const background of ["--bg-solid", "--card-solid", "--bar-solid", "--field-bg"]) {
      it(`strong edges on ${background} reach 3:1`, () => meets(value("--edge-strong"), value(background), 3));
    }
    for (const foreground of ["--citron", "--search-focus"]) {
      for (const background of ["--bg-solid", "--card-solid", "--bar-solid", "--field-bg", "--mist", "--band-start", "--band-end", "--focus-edge"]) {
        it(`${foreground} focus ring on ${background} reaches 3:1`, () => meets(value(foreground), value(background), 3));
      }
    }
    for (const foreground of ["--map-control-ink", "--map-control-disabled", "--map-attribution-ink", "--map-link"]) {
      for (const background of ["--map-control-bg", "--map-control-hover"]) {
        it(`${foreground} on ${background} reaches 4.5:1`, () => meets(value(foreground), value(background)));
      }
    }
    it("map control edges reach 3:1", () => meets(value("--map-control-line"), value("--map-control-hover"), 3));
    for (const background of ["--band-start", "--band-end"]) {
      for (const foreground of ["--band-waiting", "--band-attention"]) {
        it(`${foreground} status icon on ${background} reaches 3:1`, () => meets(value(foreground), value(background), 3));
      }
    }
  }
});

describe("pre-metal print palette", () => {
  it("restores the entire light print palette even when the phone prefers dark", () => {
    const printedLight = rootTokens("print", "light");
    const printedDark = rootTokens("print", "dark");
    expect(Object.keys(printedDark).sort()).toEqual(Object.keys(printedLight).sort());
    for (const name of Object.keys(printedLight)) {
      expect(tokenValue(printedDark, `var(${name})`), name).toBe(tokenValue(printedLight, `var(${name})`));
    }
    // Every dark override must have an explicit reset, including artwork and encoded input icons.
    const resetNames = new Set<string>();
    const darkNames = new Set<string>();
    for (const sheet of sheets) {
      sheet.walkAtRules("media", (media) => {
        const names = media.params === "print" ? resetNames
          : media.params === "(prefers-color-scheme: dark)" ? darkNames : undefined;
        if (!names) return;
        media.walkRules(":root", (rule) => { rule.walkDecls(/^--/, ({ prop }) => { names.add(prop); }); });
      });
    }
    expect(darkNames.size).toBeGreaterThan(0);
    expect([...darkNames].filter((name) => !resetNames.has(name))).toEqual([]);
  });
  it("opts native controls into both screen schemes and forces light on paper", () => {
    const schemes: string[] = [];
    sheets[0]!.walkRules(":root", (rule) => {
      rule.walkDecls("color-scheme", ({ value }) => { schemes.push(value); });
    });
    expect(schemes).toEqual(["light dark", "light"]);
  });
  it("retains every pre-Cedar resolved print token (K7)", () => {
    const printed = rootTokens("print");
    // Fingerprint at 12669f0; Cedar colours and MR-11 spacing have no print consumers.
    const snapshot = Object.keys(printed).filter((name) => !/^--(?:band(?:-|$)|mint-ink$|space-[1-6]$|on-mint$|focus-edge$|search-focus$|solid-bg$|board-bg$|nav-(?:bg|ink|tint-ink)$|active-tab-bg$|badge-(?:bg|ink)$|desk-title-ink$|map-)/.test(name))
      .sort().map((name) => [name, tokenValue(printed, `var(${name})`)]);
    expect(createHash("sha256").update(JSON.stringify(snapshot)).digest("hex"))
      .toBe("3908e7d1e99cf01ac06dd2d28b87af5f8f96601f2f9f53b5ad57fe3276082823");
  });
  it("never applies the compact spacing scale to printed content", () => {
    const consumers: string[] = [];
    for (const sheet of sheets) {
      sheet.walkDecls((declaration) => {
        if (!declaration.prop.startsWith("--") && applies(declaration, "print") && /var\(--space-[1-6]\)/.test(declaration.value)) {
          consumers.push(`${declaration.prop}: ${declaration.value}`);
        }
      });
    }
    expect(consumers).toEqual([]);
  });
  it("restores every changed original token after the Map cascade", () => {
    const printed = rootTokens("print");
    const original: Record<string, string> = {
      "--surface": "#ffffff", "--ink": "#13262f", "--muted": "#4f6169",
      "--blue": "#2455d6", "--blue-deep": "#173b98", "--mist": "#e4ecfb",
      "--line": "#d5deda", "--line-strong": "#8e9c98",
      "--bg": "#f2f5f3", "--bar": "#ffffff", "--card": "#ffffff", "--chip": "#ffffff",
      "--field-bg": "#ffffff", "--edge": "#d5deda", "--edge-strong": "#8e9c98",
      "--accent": "#13262f", "--accent-hover": "#0a1a21", "--accent-ink": "#fff",
      "--card-shadow": "none", "--bar-shadow": "0 1px 0 rgb(19 38 47 / .04)",
      "--raise-shadow": "0 1px 0 rgb(19 38 47 / .05), 0 8px 20px rgb(19 38 47 / .07)",
      "--rail-bg": "#f2f5f3", "--rail-shadow": "none",
      "--phone-bar-shadow": "0 -6px 18px rgb(19 38 47 / .06)",
      "--more-sheet-shadow": "0 -10px 30px rgb(19 38 47 / .16)",
    };
    for (const [name, value] of Object.entries(original)) {
      expect(tokenValue(printed, `var(${name})`), name).toBe(value);
    }
    for (const [companion, originalName] of Object.entries({
      "--bg-solid": "--bg", "--bar-solid": "--bar", "--card-solid": "--card",
      "--chip-solid": "--chip", "--accent-edge": "--accent", "--accent-hover-edge": "--accent-hover",
    })) {
      expect(tokenValue(printed, `var(${companion})`), companion).toBe(tokenValue(printed, `var(${originalName})`));
    }
  });
});

describe("gradient token consumers", () => {
  it("uses gradients only as top-level background images or existing masks", () => {
    const kit = postcss.parse(readFileSync(resolve(__dirname, "listKit.css"), "utf8"));
    const failures: string[] = [];
    for (const sheet of [...sheets, kit]) {
      sheet.walkDecls((declaration) => {
        if (declaration.prop.startsWith("--") || !applies(declaration, "screen")) return;
        const value = tokenValue(light, declaration.value);
        if (!value.includes("-gradient(")) return;
        const location = `${declaration.source?.input.file}:${declaration.source?.start?.line}`;
        if (!/^(?:background(?:-image)?|(?:-webkit-)?mask(?:-image)?)$/.test(declaration.prop)) {
          failures.push(`${location}: gradient in ${declaration.prop}`);
        }
        const functions: string[] = [];
        for (const match of value.matchAll(/[a-z-]+\(|[()]/gi)) {
          if (match[0] === ")") functions.pop();
          else {
            if (match[0].includes("-gradient(") && functions.length) failures.push(`${location}: nested gradient`);
            functions.push(match[0]);
          }
        }
      });
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });
});
