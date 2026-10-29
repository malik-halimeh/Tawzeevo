import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { SortMenu } from "./SortMenu";

const OPTIONS = [{ value: "newest", label: "Newest" }, { value: "oldest", label: "Oldest" }, { value: "amount", label: "Largest amount" }] as const;

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

test("the sort button names the current order and opens a single-choice menu on the checked option", () => {
  render(<SortMenu onChange={vi.fn()} options={OPTIONS} value="oldest" />);
  const button = screen.getByRole("button", { name: "Sort by Oldest" });
  expect(button).toHaveAttribute("aria-haspopup", "menu");
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("menu", { name: "Sort by" })).toBeVisible();
  const items = screen.getAllByRole("menuitemradio");
  expect(items.map((item) => item.getAttribute("aria-checked"))).toEqual(["false", "true", "false"]);
  expect(screen.getByRole("menuitemradio", { name: "Oldest" })).toHaveFocus();
});

test("arrows move through the options, Enter chooses one and focus returns to the button", () => {
  const onChange = vi.fn();
  render(<SortMenu onChange={onChange} options={OPTIONS} value="newest" />);
  const button = screen.getByRole("button", { name: "Sort by Newest" });
  fireEvent.keyDown(button, { key: "ArrowDown" });
  const menu = screen.getByRole("menu");
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(screen.getByRole("menuitemradio", { name: "Oldest" })).toHaveFocus();
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(screen.getByRole("menuitemradio", { name: "Newest" })).toHaveFocus();
  fireEvent.keyDown(menu, { key: "End" });
  expect(screen.getByRole("menuitemradio", { name: "Largest amount" })).toHaveFocus();
  fireEvent.keyDown(menu, { key: "Enter" });
  expect(onChange).toHaveBeenCalledExactlyOnceWith("amount");
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(button).toHaveFocus();
});

test("Escape and a tap outside close the menu without changing the order", () => {
  const onChange = vi.fn();
  render(<><SortMenu onChange={onChange} options={OPTIONS} value="newest" /><p>Outside</p></>);
  const button = screen.getByRole("button", { name: "Sort by Newest" });
  fireEvent.click(button);
  fireEvent.keyDown(screen.getByRole("menu"), { key: "ArrowDown" });
  fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(button).toHaveFocus();
  fireEvent.click(button);
  fireEvent.pointerDown(screen.getByText("Outside"));
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  fireEvent.click(button);
  fireEvent.click(screen.getByRole("menuitemradio", { name: "Newest" }));
  expect(onChange).not.toHaveBeenCalled();
});

test("in Arabic the button and menu carry Arabic names", async () => {
  await i18n.changeLanguage("ar");
  const onChange = vi.fn();
  render(<div dir="rtl"><SortMenu onChange={onChange} options={[{ value: "newest", label: "الأحدث" }, { value: "oldest", label: "الأقدم" }]} value="newest" /></div>);
  fireEvent.click(screen.getByRole("button", { name: "الترتيب حسب الأحدث" }));
  expect(screen.getByRole("menu", { name: "الترتيب حسب" }).closest("[dir]")).toHaveAttribute("dir", "rtl");
  fireEvent.click(screen.getByRole("menuitemradio", { name: "الأقدم" }));
  expect(onChange).toHaveBeenCalledWith("oldest");
});
