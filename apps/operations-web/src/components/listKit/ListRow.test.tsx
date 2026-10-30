import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { ListRow } from "./ListRow";

const inList = (row: ReactNode) => render(<MemoryRouter><ul className="list-rows">{row}</ul></MemoryRouter>);

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

test("the whole row is one link with title, sub-line, amount and status", () => {
  inList(<ListRow amount="USD 120.00" href="/invoices/1" status="overdue" subline="INV-0042" title="Rami Store" />);
  const link = screen.getByRole("link", { name: /Rami Store/ });
  expect(link).toHaveAttribute("href", "/invoices/1");
  expect(within(link).getByText("Rami Store")).toHaveAttribute("dir", "auto");
  expect(within(link).getByText("INV-0042")).toBeVisible();
  expect(within(link).getByText("USD 120.00")).toHaveAttribute("dir", "ltr");
  expect(within(link).getByText("Overdue")).toHaveClass("status-badge", "status-overdue");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("a row can open with a button, and its ⋮ button names the row and opens its actions", () => {
  const onOpen = vi.fn();
  const onSelect = vi.fn();
  inList(<ListRow actions={[{ label: "Share", icon: "chat", onSelect }, { label: "Open customer", href: "/customers/7" }]} onOpen={onOpen} title="Rami Store" />);
  fireEvent.click(screen.getByRole("button", { name: /^Rami Store/ }));
  expect(onOpen).toHaveBeenCalledTimes(1);

  const more = screen.getByRole("button", { name: "More actions for Rami Store" });
  expect(more).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(more);
  const menu = screen.getByRole("group", { name: "More actions for Rami Store" });
  expect(more).toHaveAttribute("aria-expanded", "true");
  expect(within(menu).getByRole("button", { name: "Share" })).toHaveFocus();
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(within(menu).getByRole("link", { name: "Open customer" })).toHaveFocus();
  fireEvent.keyDown(menu, { key: "ArrowDown" });
  expect(within(menu).getByRole("button", { name: "Share" })).toHaveFocus();
  fireEvent.keyDown(menu, { key: "Escape" });
  expect(screen.queryByRole("group", { name: "More actions for Rami Store" })).not.toBeInTheDocument();
  expect(more).toHaveFocus();

  fireEvent.click(more);
  fireEvent.click(screen.getByRole("button", { name: "Share" }));
  expect(onSelect).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("group", { name: "More actions for Rami Store" })).not.toBeInTheDocument();
  expect(more).toHaveFocus();
});

test("a danger action asks once through ConfirmAction before it runs", () => {
  const onSelect = vi.fn();
  inList(<ListRow actions={[{ label: "Delete draft", onSelect, danger: true, confirmLabel: "Yes, delete", confirmNote: "The draft is removed." }]} href="/invoices/1" title="Rami Store" />);
  const more = screen.getByRole("button", { name: "More actions for Rami Store" });
  fireEvent.click(more);
  fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));
  expect(onSelect).not.toHaveBeenCalled();
  expect(screen.getByText("The draft is removed.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Yes, delete" })).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Keep" }));
  expect(onSelect).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Delete draft" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
  expect(onSelect).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("button", { name: "Delete draft" })).not.toBeInTheDocument();
  expect(more).toHaveFocus();
});

test("a tap outside closes the action menu", () => {
  render(<MemoryRouter><ul><ListRow actions={[{ label: "Share", onSelect: vi.fn() }]} href="/a" title="Rami Store" /></ul><p>Elsewhere</p></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "More actions for Rami Store" }));
  fireEvent.pointerDown(screen.getByText("Elsewhere"));
  expect(screen.queryByRole("button", { name: "Share" })).not.toBeInTheDocument();
});

test("in Arabic the ⋮ button and status are Arabic and the amount stays left-to-right", async () => {
  await i18n.changeLanguage("ar");
  render(<MemoryRouter><div dir="rtl"><ul><ListRow actions={[{ label: "مشاركة", onSelect: vi.fn() }]} amount="120.00 USD" href="/invoices/1" status="overdue" title="متجر رامي" /></ul></div></MemoryRouter>);
  const link = screen.getByRole("link", { name: /متجر رامي/ });
  expect(link.closest("[dir='rtl']")).not.toBeNull();
  expect(within(link).getByText("متأخر")).toBeVisible();
  expect(within(link).getByText("120.00 USD")).toHaveAttribute("dir", "ltr");
  fireEvent.click(screen.getByRole("button", { name: "إجراءات أخرى لـ متجر رامي" }));
  expect(screen.getByRole("button", { name: "مشاركة" })).toHaveFocus();
});
