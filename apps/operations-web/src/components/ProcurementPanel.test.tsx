import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { PickupPanel } from "./PickupPanel";
import { ProcurementPanel } from "./ProcurementPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const line = {
  id: "l1", product_id: "p1", product_name: "Cedar Water", supplier_id: "s1", supplier_name: "Bekaa", price_basis: "PIECE", pieces_per_box: null,
  origin: "DEMAND", required_quantity: "5.0000", target_quantity: "5.0000", purchased_quantity: "0.0000", remaining_quantity: "5.0000", demand_invoice_count: 2,
  removed_at: null, remove_reason: null as string | null, waived_at: null as string | null, waive_reason: null as string | null, carried_from_item_id: null, carried_to_item_id: null, notes: null, version: 1,
  estimate: { supplier_id: "s1", supplier_name: "Bekaa", unit_cost: "8.0000", currency: "USD", age_days: 3, is_stale: false, source_type: "MANUAL", remaining_cost: "40.0000", supplier_is_recommended: false },
};
const detail = { id: "list-1", status: "OPEN", title: "Friday run", demand_from: "2026-09-19", demand_to: "2026-09-19", notes: null, assignee: null as null | Record<string, unknown>, carried_from_list_id: null, version: 1, created_at: "2026-09-19T00:00:00Z", cancel_reason: null, items: [line], estimated_totals: { USD: "40.0000" }, open_line_count: 1 };

test("owner builds a list from demand, edits the target, waives with a reason and completes", async () => {
  await i18n.changeLanguage("en");
  const calls: { method: string; path: string; body: Record<string, unknown> | undefined }[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    calls.push({ method: init?.method ?? "GET", path, body });
    if (path.endsWith("/procurement/lists") && init?.method === "POST") return Promise.resolve(Response.json(detail, { status: 201 }));
    if (path.endsWith("/procurement/lists")) return Promise.resolve(Response.json({ lists: [{ id: "list-1", status: detail.status, title: "Friday run", demand_from: "2026-09-19", demand_to: "2026-09-19", assignee: null, created_at: "2026-09-19T00:00:00Z", line_count: 1, open_line_count: detail.open_line_count }] }));
    if (path.endsWith("/procurement/assignees")) return Promise.resolve(Response.json({ assignees: [{ membership_id: "m1", role: "owner", display_name: "Layla Haddad", is_self: true }] }));
    if (path.endsWith("/suppliers")) return Promise.resolve(Response.json({ suppliers: [{ id: "s1", name: "Bekaa" }] }));
    if (path.includes("/tenants/t1/products")) return Promise.resolve(Response.json({ products: [] }));
    if (path.endsWith("/items/l1") && init?.method === "PATCH") { line.target_quantity = String(body?.target_quantity) + ".0000"; line.remaining_quantity = line.target_quantity; line.version = 2; return Promise.resolve(Response.json(detail)); }
    if (path.endsWith("/items/l1/waive")) { line.waived_at = "2026-09-19T01:00:00Z"; line.waive_reason = String(body?.reason); detail.open_line_count = 0; return Promise.resolve(Response.json(detail)); }
    if (path.endsWith("/list-1/complete")) { detail.status = "COMPLETE"; return Promise.resolve(Response.json(detail)); }
    if (path.endsWith("/lists/list-1")) return Promise.resolve(Response.json(detail));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<ProcurementPanel tenantId="t1" />);
  fireEvent.click(await screen.findByRole("button", { name: "Build from confirmed demand" }));
  expect(await screen.findByText("List built from confirmed demand.")).toBeInTheDocument();
  expect(screen.getByText((_, node) => node?.tagName === "SMALL" && /2 invoices/.test(node.textContent ?? ""))).toBeInTheDocument();
  expect(screen.getAllByText(/40\.0000 USD/).length).toBeGreaterThan(0); // labelled estimate
  expect(screen.getByRole("table").textContent).not.toMatch(/stock|on hand|available/i); // demand and progress only

  const target = screen.getByLabelText("Target for Cedar Water");
  fireEvent.change(target, { target: { value: "8" } });
  fireEvent.blur(target);
  expect(await screen.findByText("Target saved; the demand figure is unchanged.")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ expected_version: 1, target_quantity: "8" });
  expect(screen.getByText("5.0000")).toBeInTheDocument(); // required stays

  expect(screen.getByRole("button", { name: "Waive" })).toBeDisabled(); // a reason is required
  fireEvent.change(screen.getByLabelText("Reason (needed to waive, remove or cancel)"), { target: { value: "supplier closed" } });
  fireEvent.click(screen.getByRole("button", { name: "Waive" }));
  expect(await screen.findByText("Line waived with your reason.")).toBeInTheDocument();
  expect(calls.find((c) => c.path.endsWith("/waive"))?.body).toEqual({ reason: "supplier closed" });
  fireEvent.click(screen.getByRole("button", { name: "Mark complete" }));
  expect(await screen.findByText("List complete.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getAllByText("Complete").length).toBeGreaterThan(0));
});

test("driver pickup view shows suppliers and quantities only", async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ lists: [{ list_id: "list-1", title: "Friday run", status: "OPEN", notes: null, suppliers: [{ supplier_id: "s1", supplier_name: "Bekaa", contact_name: "Abu Ali", contact_phone: "+9613123456", address: "Zahle", latitude: "33.846000", longitude: "35.902000", items: [{ item_id: "l1", product_name: "Cedar Water", price_basis: "BOX", pieces_per_box: 12, remaining_quantity: "3.0000", notes: null }] }] }] }))));
  render(<PickupPanel tenantId="t1" />);
  expect(await screen.findByText("Bekaa")).toBeInTheDocument();
  expect(screen.getByText("3.0000")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open in maps" })).toHaveAttribute("href", "https://www.google.com/maps?q=33.846000,35.902000");
  expect(screen.queryByText(/USD|cost|estimate/i)).not.toBeInTheDocument();
});
