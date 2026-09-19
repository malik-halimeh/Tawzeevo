import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { MyWorkPanel } from "./MyWorkPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const task = { id: "t1", status: "ASSIGNED", official_invoice_number: "2026-000007", customer_name: "Corner Shop", customer_phone: "+96170000001", customer_address: "Hamra", customer_latitude: "33.895000", customer_longitude: "35.478000", delivery_date: "2026-09-19", route_sequence: 2, currency: "USD", amount_to_collect: "30.0000", items: [{ product_name: "Labneh", quantity: "3.0000", price_basis: "PIECE", pieces_per_box: null }], notes: null, version: 1 };

test("driver sees only assigned stops with contact, items and amount, and completes with the version", async () => {
  await i18n.changeLanguage("en");
  const bodies: Record<string, unknown>[] = [];
  let done = false;
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    if (body) bodies.push(body);
    if (path.endsWith("/my-work")) return Promise.resolve(Response.json({ tasks: done ? [] : [task], membership_id: "m2", role: "driver" }));
    if (path.endsWith("/t1/complete")) { done = true; return Promise.resolve(Response.json({ ...task, status: "COMPLETED", version: 2 })); }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<MyWorkPanel membershipId="m2" tenantId="t1" />);
  expect(await screen.findByText(/2\. Corner Shop/)).toBeInTheDocument();
  expect(screen.getByText(/3\.0000 × Labneh/)).toBeInTheDocument();
  expect(screen.getByText(/30\.0000 USD/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open in maps" })).toHaveAttribute("href", "https://www.google.com/maps?q=33.895000,35.478000");
  expect(document.body.textContent).not.toMatch(/cost|margin|profit/i);
  fireEvent.change(screen.getByLabelText("Note for the next completion (optional)"), { target: { value: "paid cash" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark delivered" }));
  expect(await screen.findByText("Marked delivered.")).toBeInTheDocument();
  expect(bodies[0]).toEqual({ expected_version: 1, note: "paid cash" });
  expect(await screen.findByText("Nothing assigned to you right now.")).toBeInTheDocument();
});
