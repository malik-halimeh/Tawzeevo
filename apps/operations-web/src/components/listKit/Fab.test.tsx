import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { Fab } from "./Fab";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

test("the add button carries its label as its name and as a visible tooltip", () => {
  const onSelect = vi.fn();
  render(<Fab label="New invoice" onSelect={onSelect} />);
  const button = screen.getByRole("button", { name: "New invoice" });
  expect(button).toHaveClass("fab");
  expect(within(button).getByText("New invoice")).toHaveClass("fab-tip");
  expect(within(button).getByText("New invoice")).toHaveAttribute("aria-hidden", "true");
  fireEvent.click(button);
  expect(onSelect).toHaveBeenCalledTimes(1);
});

test("the add button can be a link", () => {
  render(<MemoryRouter><Fab href="/invoices/new" label="New invoice" /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "New invoice" })).toHaveAttribute("href", "/invoices/new");
});

test("with a menu it opens a short list of labelled actions, closes on Escape and after a choice", () => {
  const invoice = vi.fn();
  render(<MemoryRouter><Fab label="Add" menu={[{ label: "New invoice", icon: "invoice", onSelect: invoice }, { label: "New customer", icon: "person", href: "/customers/new" }]} /></MemoryRouter>);
  const button = screen.getByRole("button", { name: "Add" });
  expect(button).toHaveAttribute("aria-expanded", "false");
  fireEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  const menu = screen.getByRole("group", { name: "Add" });
  expect(within(menu).getByRole("button", { name: "New invoice" })).toHaveFocus();
  expect(within(menu).getByRole("link", { name: "New customer" })).toHaveAttribute("href", "/customers/new");
  fireEvent.keyDown(menu, { key: "Escape" });
  expect(screen.queryByRole("group", { name: "Add" })).not.toBeInTheDocument();
  expect(button).toHaveFocus();
  fireEvent.click(button);
  fireEvent.click(screen.getByRole("button", { name: "New invoice" }));
  expect(invoice).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole("group", { name: "Add" })).not.toBeInTheDocument();
});

test("in Arabic the add button keeps its Arabic label and sits in a right-to-left page", async () => {
  await i18n.changeLanguage("ar");
  render(<div dir="rtl"><Fab label="فاتورة جديدة" onSelect={vi.fn()} /></div>);
  const button = screen.getByRole("button", { name: "فاتورة جديدة" });
  expect(button.closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(button.parentElement).toHaveClass("fab-dock");
});
