import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { BalanceChips, SupplierPaymentHistory } from "./SupplierPaymentHistory";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const row = (id: string, overrides: Record<string, unknown> = {}) => ({
  id, supplier_id: "s1", supplier_name: "Bekaa Wholesale", direction: "SUPPLIER_PAYMENT", currency: "USD", amount: "5.0000",
  paid_at: "2026-09-20T10:00:00Z", recorded_at: "2026-09-20T10:00:00Z", method: "CASH", reference: null, notes: null,
  prepayment: false, reverses_payment_id: null, reversed_by_payment_id: null, ...overrides,
});

test("the owner sees supplier payments, filters and pages them, and reverses one with a reason (D-100)", async () => {
  await i18n.changeLanguage("en");
  const requests: { path: string; body?: Record<string, unknown> }[] = [];
  let reversed = false;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    requests.push({ path, ...(body ? { body } : {}) });
    if (path.includes("/supplier-payments/p1/reverse")) { reversed = true; return Promise.resolve(Response.json(row("r1", { direction: "SUPPLIER_PAYMENT_REVERSAL", reverses_payment_id: "p1" }), { status: 201 })); }
    if (path.includes("/api/v1/payments/supplier-payments")) {
      const page = new URL(path, "http://x").searchParams.get("page");
      const payments = page === "2" ? [row("p9", { amount: "1.0000" })] : reversed
        ? [row("r1", { direction: "SUPPLIER_PAYMENT_REVERSAL", reverses_payment_id: "p1" }), row("p1", { reversed_by_payment_id: "r1" }), row("p2", { prepayment: true, amount: "3.0000" })]
        : [row("p1"), row("p2", { prepayment: true, amount: "3.0000" })];
      return Promise.resolve(Response.json({ page: Number(page), limit: 20, total: 21, total_pages: 2, payments }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
  let version = 0;
  const onChanged = vi.fn(() => { version += 1; });
  const suppliers = [{ id: "s1", name: "Bekaa Wholesale" }, { id: "s2", name: "Tyre Farms" }];
  const view = render(<SupplierPaymentHistory onChanged={onChanged} suppliers={suppliers} tenantId="t" version={version} />);

  const list = await screen.findByRole("list", { name: "Supplier payment history" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(2);
  expect(within(list).getByText("Prepayment")).toBeInTheDocument();
  expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();

  // Reverse the first payment: a reason is required, then a second confirmation.
  fireEvent.click(within(list).getAllByRole("button", { name: "Reverse this payment" })[0]!);
  const confirm = screen.getAllByRole("button", { name: "Reverse this payment" }).find((button) => button.className.includes("button-danger"))!;
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Required reversal reason"), { target: { value: "Paid twice by mistake" } });
  fireEvent.click(confirm);
  fireEvent.click(screen.getByRole("button", { name: "Yes, reverse this payment" }));
  await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  const reverseCall = requests.find((request) => request.path.includes("/p1/reverse"))!;
  expect(reverseCall.body).toMatchObject({ reason: "Paid twice by mistake" });
  expect(typeof reverseCall.body?.idempotency_key).toBe("string");

  // The parent bumps the version; the list reloads and shows the reversal and the reversed payment.
  view.rerender(<SupplierPaymentHistory onChanged={onChanged} suppliers={suppliers} tenantId="t" version={version} />);
  expect(await screen.findByText("Reversed")).toBeInTheDocument();
  expect(screen.getByText("Reversal")).toBeInTheDocument();
  // Neither the reversal nor the reversed payment can be reversed again; only p2 can.
  expect(within(screen.getByRole("list", { name: "Supplier payment history" })).getAllByRole("button", { name: "Reverse this payment" })).toHaveLength(1);

  // Filter by supplier resets to page 1 and sends supplier_id; Next asks for page 2.
  fireEvent.change(screen.getByLabelText("Show payments for"), { target: { value: "s2" } });
  await waitFor(() => expect(requests.some((request) => request.path.includes("supplier_id=s2") && request.path.includes("page=1"))).toBe(true));
  fireEvent.click(await screen.findByRole("button", { name: "Next" }));
  await waitFor(() => expect(screen.getByText("Page 2 of 2")).toBeInTheDocument());
  expect(requests.at(-1)?.path).toContain("page=2");
  expect(requests.at(-1)?.path).toContain("supplier_id=s2");
});

test("balance chips show each currency separately, or a short note when there is none", async () => {
  await i18n.changeLanguage("en");
  const { rerender } = render(<BalanceChips balances={[{ currency: "LBP", balance: "900000.0000" }, { currency: "USD", balance: "21.0000" }]} />);
  expect(screen.getByText("900000.0000 LBP")).toBeInTheDocument();
  expect(screen.getByText("21.0000 USD")).toBeInTheDocument();
  rerender(<BalanceChips balances={[]} />);
  expect(screen.getByText(/no balance yet/)).toBeInTheDocument();
});
