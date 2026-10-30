import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Arrow, Icon, type IconName } from "./Icon";
import { PATHS } from "./iconGeometry";

const names = Object.keys(PATHS) as IconName[];
afterEach(cleanup);

describe("solid icon family", () => {
  it.each(names)("renders %s as a decorative solid SVG", (name) => {
    const { container } = render(<Icon name={name} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("icon", "icon-solid");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(svg).toHaveAttribute("viewBox", "0 0 24 24");
    expect(svg?.querySelector("g > path, g > circle, g > rect")).not.toBeNull();
  });

  it("composes small and caller classes and forwards SVG props", () => {
    const { container } = render(<Icon name="invoice" small className="caller-icon" data-testid="invoice" width={48} />);
    expect(container.querySelector("svg")).toHaveClass("icon", "icon-solid", "icon-small", "caller-icon");
    expect(container.querySelector("svg")).toHaveAttribute("width", "48");
    expect(container.querySelector("svg")).toHaveAttribute("data-testid", "invoice");
  });

  it("keeps every mask unique and locally referenced when the whole family renders twice", () => {
    const { container, rerender } = render(<>{names.flatMap((name) => [<Icon key={`${name}-a`} name={name} />, <Icon key={`${name}-b`} name={name} />])}</>);
    const ids = Array.from(container.querySelectorAll("mask"), (mask) => mask.id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length);
    for (const svg of container.querySelectorAll("svg")) {
      const mask = svg.querySelector("mask");
      if (mask) {
        expect(svg.querySelector("g[mask]")).toHaveAttribute("mask", `url(#${mask.id})`);
        expect(mask).toHaveAttribute("maskUnits", "userSpaceOnUse");
      }
    }
    rerender(<><Icon name="invoice" /><Icon name="invoice" /></>);
    const pair = Array.from(container.querySelectorAll("mask"), (mask) => mask.id);
    expect(pair).toHaveLength(2);
    expect(new Set(pair).size).toBe(2);
  });

  it("preserves the directional wrapper for forward and back arrows", () => {
    const { container } = render(<><Arrow /><Arrow back small /></>);
    const arrows = container.querySelectorAll(".directional > svg");
    expect(arrows).toHaveLength(2);
    expect(arrows[0]?.querySelector("path")).toHaveAttribute("d", "M5 12h14m-6-6 6 6-6 6");
    expect(arrows[1]?.querySelector("path")).toHaveAttribute("d", "M19 12H5m6-6-6 6 6 6");
    expect(arrows[1]).toHaveClass("icon-small");
  });
});
