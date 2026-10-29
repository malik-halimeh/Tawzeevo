import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test } from "vitest";

import i18n from "../../i18n";
import { ListRow } from "./ListRow";
import { MonthGroup } from "./MonthGroup";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

test("a month group names its month, shows its total left-to-right and lists its rows", () => {
  render(<MemoryRouter><MonthGroup month="2026-10" total="USD 1,240.00"><ListRow href="/a" title="Rami Store" /><ListRow href="/b" title="Hana Market" /></MonthGroup></MemoryRouter>);
  const group = screen.getByRole("region", { name: "October 2026" });
  expect(within(group).getByRole("heading", { level: 2, name: "October 2026" })).toBeVisible();
  expect(within(group).getByText("Month total")).toHaveClass("sr-only");
  expect(within(group).getByText("USD 1,240.00")).toHaveAttribute("dir", "ltr");
  expect(within(within(group).getByRole("list")).getAllByRole("listitem")).toHaveLength(2);
});

test("a full date key groups by its month, and the heading level can be lowered", () => {
  render(<MonthGroup level={3} month="2026-01-31"><li>Row</li></MonthGroup>);
  expect(screen.getByRole("heading", { level: 3, name: "January 2026" })).toBeVisible();
});

test("in Arabic the month is written with its Arabic name", async () => {
  await i18n.changeLanguage("ar");
  render(<div dir="rtl"><MonthGroup month="2026-10" total="1,240.00"><li>صف</li></MonthGroup></div>);
  const heading = screen.getByRole("heading", { level: 2 });
  expect(heading.textContent).toContain("تشرين الأول");
  expect(heading.textContent).toBe(new Intl.DateTimeFormat("ar-LB", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(2026, 9, 1))));
  expect(screen.getByText("مجموع الشهر")).toHaveClass("sr-only");
});
