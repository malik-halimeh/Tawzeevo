import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../../i18n";
import { FilterSheet } from "./FilterSheet";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(cleanup);

function renderSheet(activeCount: number, handlers: { onApply?: () => void; onClear?: () => void; onClose?: () => void } = {}) {
  return render(
    <FilterSheet activeCount={activeCount} onApply={handlers.onApply ?? vi.fn()} onClear={handlers.onClear ?? vi.fn()} onClose={handlers.onClose ?? vi.fn()}>
      <label className="field"><span>From date</span><input type="date" /></label>
    </FilterSheet>,
  );
}

test("the Filters button tells how many filters are in use", () => {
  const { rerender } = renderSheet(2);
  expect(screen.getByRole("button", { name: "Filters 2 active" })).toHaveAttribute("aria-haspopup", "dialog");
  rerender(<FilterSheet activeCount={0} onApply={vi.fn()} onClear={vi.fn()}><span /></FilterSheet>);
  expect(screen.getByRole("button", { name: "Filters" })).toBeVisible();
});

test("the sheet is a labelled dialog that keeps focus inside and returns it to the button on Escape", () => {
  const onClose = vi.fn();
  renderSheet(1, { onClose });
  const opener = screen.getByRole("button", { name: "Filters 1 active" });
  fireEvent.click(opener);
  const dialog = screen.getByRole("dialog", { name: "Filters" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(screen.getByLabelText("From date")).toHaveFocus();

  const apply = screen.getByRole("button", { name: "Apply filters" });
  apply.focus();
  fireEvent.keyDown(dialog, { key: "Tab" });
  expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
  expect(apply).toHaveFocus();

  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("Clear keeps the sheet open, Apply applies and closes, Close closes without applying", () => {
  const onApply = vi.fn();
  const onClear = vi.fn();
  const onClose = vi.fn();
  renderSheet(3, { onApply, onClear, onClose });
  const opener = screen.getByRole("button", { name: "Filters 3 active" });
  fireEvent.click(opener);
  fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(onClear).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("dialog")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
  expect(onApply).toHaveBeenCalledTimes(1);
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();

  fireEvent.click(opener);
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(onApply).toHaveBeenCalledTimes(1);
});

test("in Arabic the button counts filters with Arabic plural forms", async () => {
  await i18n.changeLanguage("ar");
  render(<div dir="rtl"><FilterSheet activeCount={2} onApply={vi.fn()} onClear={vi.fn()}><input aria-label="من تاريخ" type="date" /></FilterSheet></div>);
  fireEvent.click(screen.getByRole("button", { name: "عوامل التصفية عاملان مفعّلان" }));
  expect(screen.getByRole("dialog", { name: "عوامل التصفية" }).closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(screen.getByRole("button", { name: "مسح" })).toBeVisible();
  expect(screen.getByRole("button", { name: "تطبيق عوامل التصفية" })).toBeVisible();
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.getByRole("button", { name: "عوامل التصفية عاملان مفعّلان" })).toHaveFocus();
});
