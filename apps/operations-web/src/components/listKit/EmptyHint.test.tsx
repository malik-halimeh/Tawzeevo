import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { EmptyState } from "../Ui";
import { EmptyHint } from "./EmptyHint";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

test("an empty hint is one line with an icon and an optional next step", () => {
  const onSelect = vi.fn();
  const { container } = render(<EmptyHint action={{ label: "New invoice", onSelect }} icon="invoice" text="No invoices this month." />);
  expect(container.firstElementChild).toHaveClass("empty-state", "empty-hint");
  expect(container.querySelector("svg.icon")).toHaveAttribute("aria-hidden", "true");
  expect(screen.getByText("No invoices this month.")).toBeVisible();
  expect(container.querySelector("p")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "New invoice" }));
  expect(onSelect).toHaveBeenCalledTimes(1);
});

test("the next step can be a link, and without one only the line shows", () => {
  const { rerender } = render(<MemoryRouter><EmptyHint action={{ label: "Add customer", href: "/customers/new" }} text="No customers yet." /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Add customer" })).toHaveAttribute("href", "/customers/new");
  rerender(<MemoryRouter><EmptyHint text="No customers yet." /></MemoryRouter>);
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

test("EmptyState keeps its existing output for existing callers", () => {
  const { container } = render(<EmptyState body="Nothing here." title="Empty" />);
  expect(container.innerHTML).toBe('<div class="empty-state"><svg aria-hidden="true" class="icon" focusable="false" viewBox="0 0 24 24"><path d="m12 3 9 5v9l-9 5-9-5V8Zm-9 5 9 5 9-5m-9 5v9M7 5.8l10 5.4"></path></svg><strong>Empty</strong><p>Nothing here.</p></div>');
});

test("in Arabic the hint reads in Arabic inside a right-to-left page", async () => {
  await i18n.changeLanguage("ar");
  render(<div dir="rtl"><EmptyHint action={{ label: "فاتورة جديدة", onSelect: vi.fn() }} text="لا فواتير هذا الشهر." /></div>);
  expect(screen.getByText("لا فواتير هذا الشهر.").closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(screen.getByRole("button", { name: "فاتورة جديدة" })).toBeVisible();
});
