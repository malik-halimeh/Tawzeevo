import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import i18n from "../../i18n";
import { InvoiceLineCard } from "./InvoiceLineCard";
import type { EditorLine } from "./editorLine";

const line: EditorLine = {
  key: "oil", productId: "oil", name: "Sunflower Oil 1.8L", quantity: "1+1", basis: "PIECE",
  unitPrice: "4.0000", lineDiscount: "0.5", lineMarkup: "0.25", supplierId: "supplier",
  costOptions: [{ supplier_id: "supplier", supplier_name: "Wholesale", is_preferred: true, product_cost_entry_id: "cost", unit_cost: "2", currency: "USD", cost_basis: "PIECE", pieces_per_box: null, effective_at: null }],
  costOverride: "2.5", costOverrideReason: "Previous purchase",
};
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScroll);
  else delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView;
});

test("expanding retains quantity, basis, totals, adjustments, supplier, override, reason and Remove", () => {
  const remove = vi.fn();
  function Line() {
    const [value, setValue] = useState(line);
    const [expanded, setExpanded] = useState(false);
    return <InvoiceLineCard expanded={expanded} highlighted={undefined} index={1} line={value} lineTotal="7.7500" onBasisChange={(basis) => setValue({ ...value, basis })} onChange={(changes) => setValue({ ...value, ...changes })} onRemove={remove} onToggle={() => setExpanded(!expanded)} suppliers={[]} totalCurrency="USD" />;
  }
  render(<Line />);
  const edit = screen.getByRole("button", { name: "Edit line 2, Sunflower Oil 1.8L" });
  expect(screen.getByText(line.name)).toHaveAttribute("dir", "auto");
  expect(edit).toHaveTextContent("× 4.00 $ Piece");
  expect(edit).toHaveTextContent("7.75 $");
  expect(screen.getByRole("group", { name: /Quantity for/ })).toHaveTextContent("2");
  expect(screen.getByLabelText("Cost override")).not.toBeVisible();
  fireEvent.click(edit);
  for (const label of ["Quantity / calculator", "Price basis", "Line discount", "Line markup", "Supplier and latest cost", "Cost override", "Required override reason"]) {
    expect(screen.getByLabelText(label)).toBeVisible();
  }
  fireEvent.change(screen.getByLabelText("Required override reason"), { target: { value: "Typed reason" } });
  const reason = screen.getByLabelText("Required override reason");
  fireEvent.click(edit);
  expect(reason).not.toBeVisible();
  fireEvent.click(edit);
  expect(screen.getByLabelText("Required override reason")).toBe(reason);
  expect(reason).toHaveValue("Typed reason");
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(remove).toHaveBeenCalledOnce();
});

test("a new line scrolls only when obscured, without animated motion", () => {
  const scroll = vi.fn();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: scroll });
  let bottom = 60;
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({ top: bottom - 56, bottom, left: 0, right: 300, width: 300, height: 56, x: 0, y: bottom - 56, toJSON: () => ({}) }));
  const props = { expanded: false, highlighted: "add-1", index: 0, line, lineTotal: "7.7500", onBasisChange: vi.fn(), onChange: vi.fn(), onRemove: vi.fn(), onToggle: vi.fn(), suppliers: [], totalCurrency: "USD" };
  const { rerender } = render(<InvoiceLineCard {...props} />);
  expect(scroll).not.toHaveBeenCalled();
  bottom = window.innerHeight + 100;
  rerender(<InvoiceLineCard {...props} highlighted="add-2" />);
  expect(scroll).toHaveBeenCalledExactlyOnceWith({ block: "nearest", behavior: "instant" });
});
