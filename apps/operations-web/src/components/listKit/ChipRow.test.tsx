import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { ChipRow } from "./ChipRow";

const CHIPS = [{ value: "all", label: "All" }, { value: "unpaid", label: "Unpaid", count: 4 }, { value: "overdue", label: "Overdue", count: 1 }] as const;
type Value = (typeof CHIPS)[number]["value"];

function Single({ onChange }: { onChange?: (value: Value) => void }) {
  const [value, setValue] = useState<Value>("all");
  return <ChipRow chips={CHIPS} label="Invoice filters" onChange={(next) => { setValue(next); onChange?.(next); }} value={value} />;
}

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

test("chips are toggle buttons in a named group; one is pressed at a time and counts stay left-to-right", () => {
  const onChange = vi.fn();
  render(<Single onChange={onChange} />);
  expect(screen.getByRole("group", { name: "Invoice filters" })).toBeVisible();
  expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  const unpaid = screen.getByRole("button", { name: "Unpaid 4" });
  expect(unpaid).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByText("4")).toHaveAttribute("dir", "ltr");
  fireEvent.click(unpaid);
  expect(unpaid).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(unpaid);
  expect(onChange).toHaveBeenCalledExactlyOnceWith("unpaid");
});

test("Left/Right arrows move between chips in reading direction and Enter-style clicks choose", () => {
  render(<Single />);
  const all = screen.getByRole("button", { name: "All" });
  all.focus();
  fireEvent.keyDown(all, { key: "ArrowRight" });
  expect(screen.getByRole("button", { name: "Unpaid 4" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "End" });
  expect(screen.getByRole("button", { name: "Overdue 1" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
  expect(screen.getByRole("button", { name: "Overdue 1" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "Home" });
  expect(all).toHaveFocus();
});

test("with multiple set, chips toggle on and off independently", () => {
  const onChange = vi.fn();
  render(<ChipRow chips={CHIPS} label="Filters" multiple onChange={onChange} value={["unpaid"]} />);
  fireEvent.click(screen.getByRole("button", { name: "Overdue 1" }));
  expect(onChange).toHaveBeenLastCalledWith(["unpaid", "overdue"]);
  fireEvent.click(screen.getByRole("button", { name: "Unpaid 4" }));
  expect(onChange).toHaveBeenLastCalledWith([]);
});

test("in Arabic the arrows follow right-to-left order", async () => {
  await i18n.changeLanguage("ar");
  render(<div dir="rtl"><ChipRow chips={[{ value: "all", label: "الكل" }, { value: "unpaid", label: "غير مدفوعة", count: 4 }]} label="عوامل التصفية" onChange={vi.fn()} value="all" /></div>);
  const all = screen.getByRole("button", { name: "الكل" });
  expect(all).toHaveAttribute("aria-pressed", "true");
  all.focus();
  fireEvent.keyDown(all, { key: "ArrowRight" });
  expect(all).toHaveFocus();
  fireEvent.keyDown(all, { key: "ArrowLeft" });
  expect(screen.getByRole("button", { name: "غير مدفوعة 4" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
  expect(all).toHaveFocus();
});
