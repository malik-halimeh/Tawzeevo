/// <reference types="node" />
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
import postcss, { type AnyNode } from "postcss";
import { describe, expect, it } from "vitest";

const sheets = ["styles.css", "map.css"].map((file) => postcss.parse(
  readFileSync(resolve(__dirname, file), "utf8"), { from: file },
));

function applies(node: AnyNode, medium: "screen" | "print"): boolean {
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (parent instanceof postcss.AtRule && parent.name === "media") {
      if (/\bprint\b/.test(parent.params) && medium !== "print") return false;
      if (/\bscreen\b/.test(parent.params) && medium !== "screen") return false;
    }
  }
  return true;
}

function rootTokens(medium: "screen" | "print"): Record<string, string> {
  const tokens: Record<string, string> = {};
  for (const sheet of sheets) {
    sheet.walkRules((rule) => {
      if (!rule.selectors.includes(":root") || !applies(rule, medium)) return;
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
const lightValue = (name: string) => tokenValue(light, `var(${name})`);

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

function stops(name: string): string[] {
  const colours = lightValue(name).match(/#[\da-f]{3}(?:[\da-f]{3})?\b/gi);
  if (!colours?.length) throw new Error(`No surface colours: ${name}`);
  return colours;
}

function meets(foreground: string, background: string, target = 4.5): void {
  const ratio = contrast(foreground, background);
  expect(ratio, `${foreground} on ${background}: ${ratio.toFixed(4)}:1, requires ${target}:1`)
    .toBeGreaterThanOrEqual(target);
}

describe("light design contrast", () => {
  it("calculates the WCAG black/white reference ratio", () => {
    expect(contrast("#000", "#fff")).toBe(21);
    expect(contrast("#fff", "#000")).toBe(21);
  });

  for (const foreground of ["--ink", "--muted"]) {
    for (const background of ["--bg-solid", "--card-solid"]) {
      it(`${foreground} on ${background} reaches 4.5:1`, () => meets(lightValue(foreground), lightValue(background)));
    }
    it(`${foreground} on the darkest bar stop reaches 4.5:1`, () => {
      const darkest = stops("--bar").reduce((a, b) => luminance(a) < luminance(b) ? a : b);
      meets(lightValue(foreground), darkest);
    });
    it(`${foreground} on the darkest page stop reaches 4.5:1`, () => {
      const darkest = stops("--bg").reduce((a, b) => luminance(a) < luminance(b) ? a : b);
      meets(lightValue(foreground), darkest);
    });
  }

  for (const background of ["--bg-solid", "--card-solid"]) {
    it(`links on ${background} reach 4.5:1`, () => meets(lightValue("--blue"), lightValue(background)));
  }
  for (const background of ["--accent", "--accent-hover"]) {
    it(`action text on every ${background} stop reaches 4.5:1`, () => {
      for (const stop of stops(background)) meets(lightValue("--accent-ink"), stop);
    });
  }
  for (const meaning of ["good", "warn", "bad"]) {
    it(`${meaning} text on its background reaches 4.5:1`, () => meets(lightValue(`--${meaning}`), lightValue(`--${meaning}-bg`)));
  }
  it("strong edges on card solid reach 3:1", () => meets(lightValue("--edge-strong"), lightValue("--card-solid"), 3));
  it("keeps Cedar surfaces flat and fields softly tinted", () => {
    for (const [name, value] of Object.entries({
      "--bg": "#f3f6f4", "--bar": "#ffffff", "--card": "#ffffff", "--chip": "#ffffff",
      "--field-bg": "#f5f8f6", "--accent": "#0f6b55", "--accent-hover": "#0b5644",
    })) expect(lightValue(name), name).toBe(value);
    for (const name of ["bg", "bar", "card", "chip", "accent"]) {
      expect(lightValue(`--${name}-solid`)).toBe(lightValue(`--${name}`));
    }
  });
  it("white text on primary reaches 4.5:1", () => meets(lightValue("--on-solid"), lightValue("--accent")));
  for (const foreground of ["--band-ink", "--band-muted"]) {
    it(`${foreground} on both band stops reaches 4.5:1`, () => {
      for (const stop of stops("--band")) meets(lightValue(foreground), stop);
    });
  }
  it("white glass-pill text on both composited band stops reaches 4.5:1", () => {
    const glass = lightValue("--band-glass").match(/^rgb\(255 255 255 \/ ([\d.]+)\)$/);
    expect(glass).not.toBeNull();
    const opacity = Number(glass![1]);
    for (const stop of stops("--band")) {
      const background = "#" + stop.slice(1).match(/../g)!.map((channel) =>
        Math.round(255 * opacity + parseInt(channel, 16) * (1 - opacity)).toString(16).padStart(2, "0"),
      ).join("");
      meets(lightValue("--band-ink"), background);
    }
  });
  it("mint ink on mint reaches 4.5:1", () => meets(lightValue("--mint-ink"), lightValue("--citron")));
  for (const foreground of ["--ink", "--muted"]) {
    it(`${foreground} on the field reaches 4.5:1`, () => meets(lightValue(foreground), lightValue("--field-bg")));
  }
});

describe("pre-metal print palette", () => {
  it("retains every pre-Cedar resolved print token (K7)", () => {
    const printed = rootTokens("print");
    // Fingerprint of all resolved print tokens at 12669f0; Cedar-only tokens have no print consumers.
    const snapshot = Object.keys(printed).filter((name) => !/^--(?:band(?:-|$)|mint-ink$)/.test(name))
      .sort().map((name) => [name, tokenValue(printed, `var(${name})`)]);
    expect(createHash("sha256").update(JSON.stringify(snapshot)).digest("hex"))
      .toBe("3908e7d1e99cf01ac06dd2d28b87af5f8f96601f2f9f53b5ad57fe3276082823");
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
