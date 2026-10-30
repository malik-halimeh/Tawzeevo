/// <reference types="node" />
import { readdirSync, readFileSync } from "node:fs";
import { relative, resolve } from "node:path";
import postcss, { type AnyNode, type Declaration } from "postcss";
import { describe, expect, it } from "vitest";

const namedColours = new Set(`aliceblue antiquewhite aqua aquamarine azure beige bisque black
  blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue
  cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki
  darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue
  darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
  firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow
  grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon
  lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
  lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen
  magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
  mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite
  navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred
  papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown
  salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen
  steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen`.split(/\s+/));

function cssFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return directory === __dirname && entry.name === "demo" ? [] : cssFiles(path);
    return entry.name.endsWith(".css") ? [path] : [];
  }).sort();
}

function inPrint(declaration: Declaration): boolean {
  for (let node: AnyNode | undefined = declaration.parent; node; node = node.parent) {
    if (node.type === "atrule" && node.name.toLowerCase() === "media"
      && node.params.split(",").every((query) => /^(?:only\s+)?print(?:\s+and\b.*)?$/i.test(query.trim()))) return true;
  }
  return false;
}

function colourLiterals(value: string): { literal: string; offset: number }[] {
  const found: { literal: string; offset: number }[] = [];
  // Skip comments, strings, external URLs and custom-property identifiers, so e.g. --white,
  // a fragment URL or content: "black" is not confused with a rendered colour.
  const tokens = /\/\*[\s\S]*?\*\/|url\(\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^)]*)\s*\)|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|--[\w-]+|#[\da-f]{3,8}\b|[a-z][\w-]*/gi;
  for (const match of value.matchAll(tokens)) {
    const token = match[0].toLowerCase();
    const offset = match.index;
    if (token.startsWith("url(")) {
      // Encoded SVG fill/stroke colours must live in image tokens too.
      if (/data:image\/svg\+xml/i.test(token)) {
        const decoded = decodeURIComponent(token);
        const attributes = [...decoded.matchAll(/(?:fill|stroke|color|style)\s*=\s*["']([^"']*)/gi)];
        if (attributes.some((attribute) => colourLiterals(attribute[1] ?? "").length > 0)) {
          found.push({ literal: match[0], offset });
        }
      }
    } else if (token.startsWith("#") || namedColours.has(token)) {
      found.push({ literal: match[0], offset });
    } else if (/^(?:rgba?|hsla?)$/.test(token)) {
      const rest = value.slice(offset + token.length);
      // Channels must all come from tokens; only opacity may be a number outside one.
      const tokenChannels = /^\s*\(\s*(?:var\(\s*--[\w-]+\s*\)\s*)+(?:(?:\/|,)\s*(?:[+-]?(?:\d*\.)?\d+%?|var\(\s*--[\w-]+\s*\)))?\s*\)/i;
      if (/^\s*\(/.test(rest) && !tokenChannels.test(rest)) found.push({ literal: match[0], offset });
    }
  }
  return found;
}

function violations(css: string, file: string): string[] {
  const failures: string[] = [];
  postcss.parse(css, { from: file }).walkDecls((declaration) => {
    if (declaration.prop.startsWith("--") || inPrint(declaration)) return;
    const mask = /^(?:-webkit-)?mask(?:-|$)/i.test(declaration.prop);
    for (const { literal, offset } of colourLiterals(declaration.value)) {
      if (mask && /^#0000?$/i.test(literal)) continue;
      const valueStart = (declaration.source?.start?.offset ?? 0) + declaration.prop.length + (declaration.raws.between?.length ?? 1);
      const line = css.slice(0, valueStart + offset).split("\n").length;
      failures.push(`${file}:${line}: ${declaration.prop}: ${literal}`);
    }
  });
  return failures;
}

describe("design tokens", () => {
  it("defines the approved six-step spacing scale", () => {
    const tokens: Record<string, string> = {};
    postcss.parse(readFileSync(resolve(__dirname, "styles.css"), "utf8")).walkRules(":root", (rule) => {
      rule.walkDecls(/^--space-/, ({ prop, value }) => { tokens[prop] = value; });
    });
    expect(tokens).toEqual({ "--space-1": "4px", "--space-2": "8px", "--space-3": "12px", "--space-4": "16px", "--space-5": "20px", "--space-6": "24px" });
  });
  it("keeps screen colour literals in custom properties throughout src, excluding src/demo", () => {
    const files = cssFiles(__dirname);
    expect(files.length).toBeGreaterThan(0);
    const failures = files.flatMap((file) => violations(readFileSync(file, "utf8"), relative(__dirname, file).replaceAll("\\", "/")));
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("reports literals in nested rules, fallbacks, gradients and shadows with their line numbers", () => {
    expect(violations(`@media screen {
  .card { color: WHITE; border: 1px solid #abc; }
  .chip { background: var(--missing, rebeccapurple); }
  .card { box-shadow: 0 1px rgba(0, 0, 0, .2); background: linear-gradient(transparent, hsl(0 0% 0%)); }
}`, "nested.css")).toEqual([
      "nested.css:2: color: WHITE", "nested.css:2: border: #abc",
      "nested.css:3: background: rebeccapurple", "nested.css:4: box-shadow: rgba", "nested.css:4: background: hsl",
    ]);
  });

  it("allows only the token, print and mask-alpha exceptions", () => {
    expect(violations(`:root { --white: #fff; --shadow: rgba(0, 0, 0, .2); }
@media print { @supports (display: grid) { .card { color: black; background: white; } } }
.card { color: currentColor; background: inherit; border-color: transparent;
  box-shadow: 0 1px rgb(var(--shadow-tint) / .2); content: "white";
  mask: linear-gradient(#000, #0000); -webkit-mask: linear-gradient(#0000, #000);
  background-image: url("/white.svg#abc"); color: var(--white); /* black */
}`, "allowed.css")).toEqual([]);
    expect(violations(".card { mask: linear-gradient(#fff, red); color: #000; }", "mask.css")).toEqual([
      "mask.css:1: mask: #fff", "mask.css:1: mask: red", "mask.css:1: color: #000",
    ]);
    expect(violations("@media not print { .card { color: black; } } @media screen, print { .card { color: white; } }", "screen.css")).toEqual([
      "screen.css:1: color: black", "screen.css:1: color: white",
    ]);
    expect(violations(".card { color: rgb(var(--r) 0 0); background: rgb(var(--channels, 0 0 0) / .2); }", "channels.css")).toEqual([
      "channels.css:1: color: rgb", "channels.css:1: background: rgb",
    ]);
  });
});
