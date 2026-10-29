import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { ListHeader, SEARCH_DELAY_MS } from "./ListHeader";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

test("the header shows the title and a counted line with the number kept left-to-right", () => {
  const { rerender } = render(<ListHeader count={12} title="Invoices" />);
  expect(screen.getByRole("heading", { level: 1, name: "Invoices" })).toBeVisible();
  expect(screen.getByText(/items/).textContent).toBe("12 items");
  expect(screen.getByText("12").tagName).toBe("BDI");
  expect(screen.getByText("12")).toHaveAttribute("dir", "ltr");
  rerender(<ListHeader count={1} title="Invoices" />);
  expect(screen.getByText(/item/).textContent).toBe("1 item");
  expect(screen.queryByRole("button", { name: "Search" })).not.toBeInTheDocument();
});

test("search opens an inline labelled field, waits for typing to stop, clears at once and closes with Escape", () => {
  vi.useFakeTimers();
  const onSearch = vi.fn();
  render(<ListHeader onSearch={onSearch} title="Invoices" />);
  const toggle = screen.getByRole("button", { name: "Search" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  const field = screen.getByRole("searchbox", { name: "Search this list" });
  expect(field).toHaveFocus();

  fireEvent.change(field, { target: { value: "ri" } });
  fireEvent.change(field, { target: { value: "rice" } });
  act(() => { vi.advanceTimersByTime(SEARCH_DELAY_MS - 1); });
  expect(onSearch).not.toHaveBeenCalled();
  act(() => { vi.advanceTimersByTime(1); });
  expect(onSearch).toHaveBeenCalledExactlyOnceWith("rice");

  fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
  expect(onSearch).toHaveBeenLastCalledWith("");
  expect(field).toHaveValue("");
  expect(field).toHaveFocus();

  fireEvent.change(field, { target: { value: "oil" } });
  fireEvent.keyDown(field, { key: "Escape" });
  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  expect(toggle).toHaveFocus();
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  act(() => { vi.advanceTimersByTime(SEARCH_DELAY_MS); });
  expect(onSearch.mock.calls.map(([text]) => text as string)).toEqual(["rice", ""]);
});

test("a remembered search starts open without taking focus, and actions and sort sit in the header", () => {
  render(<ListHeader actions={<button type="button">Export</button>} defaultSearch="rice" onSearch={vi.fn()} sort={<button type="button">Newest</button>} title="Invoices" />);
  expect(screen.getByRole("searchbox")).toHaveValue("rice");
  expect(screen.getByRole("searchbox")).not.toHaveFocus();
  expect(screen.getByRole("button", { name: "Export" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Newest" })).toBeVisible();
});

test("in Arabic the count uses Arabic plural forms and the search field has an Arabic label", async () => {
  await i18n.changeLanguage("ar");
  const { rerender } = render(<div dir="rtl"><ListHeader count={2} onSearch={vi.fn()} title="الفواتير" /></div>);
  expect(screen.getByRole("heading", { name: "الفواتير" }).closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(screen.getByText("عنصران")).toBeVisible();
  rerender(<div dir="rtl"><ListHeader count={12} onSearch={vi.fn()} title="الفواتير" /></div>);
  expect(screen.getByText(/عنصرًا/).textContent).toBe("12 عنصرًا");
  fireEvent.click(screen.getByRole("button", { name: "بحث" }));
  expect(screen.getByRole("searchbox", { name: "ابحث في هذه القائمة" })).toHaveFocus();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "أرز" } });
  expect(screen.getByRole("button", { name: "مسح البحث" })).toBeVisible();
});
