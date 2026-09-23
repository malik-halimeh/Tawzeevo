import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { type SyncOutcome, syncNow } from "../offline/pull";
import { queueDeliveryCompletion } from "../offline/supplierCommands";
import { MyWorkPanel } from "./MyWorkPanel";

// The device registration, outbox and sync engine are stubbed: these tests cover what the work screen
// shows for each sync result, not the offline protocol itself (covered by the offline module tests).
vi.mock("../offline/pull", () => ({ syncNow: vi.fn() }));
vi.mock("../offline/supplierCommands", () => ({ queueDeliveryCompletion: vi.fn(() => Promise.resolve()) }));
vi.mock("../offline/sync", () => ({ localSyncStatus: vi.fn(() => Promise.resolve({ bootstrapped_at: "2026-09-23T08:00:00Z" })), bootstrapLocalProjection: vi.fn(() => Promise.resolve()) }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.mocked(syncNow).mockReset(); vi.mocked(queueDeliveryCompletion).mockClear(); });

/** The browser's own network flag, which decides whether a failed completion is queued on the device. */
function browserOnline(online: boolean) {
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(online);
}

/** One pane (below 1100px): the open stop replaces the list. */
function onePane() {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
}

function syncResult(push: { acknowledged: number; conflicts: number; rejected?: number; failed?: number }): SyncOutcome {
  return { kind: "ok", push: { sent: 1, rejected: 0, failed: 0, high_water_change_seq: 1, ...push }, pull: { applied: 0, pages: 1, cursor: 1, rebootstrapped: false }, status: {} } as unknown as SyncOutcome;
}

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
  // The stop appears in the ordered list (with its route number) and in the selected-stop detail.
  const stop = await screen.findByRole("button", { name: /02.*Corner Shop.*30\.0000 USD/ });
  expect(stop).toHaveAttribute("aria-current", "true");
  expect(screen.getByRole("heading", { name: "Corner Shop" })).toBeInTheDocument();
  expect(screen.getByText("Labneh")).toBeInTheDocument();
  expect(screen.getByText("3.0000")).toBeInTheDocument();
  expect(screen.getAllByText(/30\.0000 USD/).length).toBeGreaterThan(0);
  expect(screen.getByText("Amount to collect")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open in maps" })).toHaveAttribute("href", "https://www.google.com/maps?q=33.895000,35.478000");
  expect(screen.getByRole("link", { name: "+96170000001" })).toHaveAttribute("href", "tel:+96170000001");
  expect(screen.getByText("2026-000007")).toHaveAttribute("dir", "ltr");
  expect(screen.getByText("0 of 1 completed")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/cost|margin|profit/i);
  fireEvent.change(screen.getByLabelText("Note for the next completion (optional)"), { target: { value: "paid cash" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark delivered" }));
  expect(await screen.findByText("Marked delivered.")).toBeInTheDocument();
  expect(bodies[0]).toEqual({ expected_version: 1, note: "paid cash" });
  expect(await screen.findByText("Nothing assigned to you right now.")).toBeInTheDocument();
  expect(screen.getByText("1 of 1 completed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Mark delivered" })).not.toBeInTheDocument();
});

test("a phone user opens one stop at a time and can return to the list; Arabic mirrors the copy", async () => {
  await i18n.changeLanguage("ar");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ tasks: [task, { ...task, id: "t2", customer_name: "Second Stop", route_sequence: 3 }], membership_id: "m2", role: "driver" }))));
  render(<MyWorkPanel membershipId="m2" tenantId="t1" />);
  const second = await screen.findByRole("button", { name: /03.*Second Stop/ });
  fireEvent.click(second);
  const panel = screen.getByRole("region", { name: "مساري" });
  expect(panel).toHaveClass("show-detail");
  expect(screen.getByRole("heading", { name: "Second Stop" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "زيارة. تتبعها أخرى." })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "كل الزيارات" }));
  expect(panel).not.toHaveClass("show-detail");
  expect(screen.getByRole("button", { name: "تعليم كمُسلَّم" })).toBeInTheDocument();
  expect(screen.getByText("+96170000001", { selector: "span" })).toHaveAttribute("dir", "ltr");
  await i18n.changeLanguage("en");
});

const second = { ...task, id: "t2", customer_name: "Second Stop", route_sequence: 3 };

/** Queues the first stop's completion while the browser is offline, then comes back online. */
async function queueFirstStopOffline(delivered: { value: boolean }) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    if (path.endsWith("/my-work")) return Promise.resolve(Response.json({ tasks: delivered.value ? [second] : [task, second], membership_id: "m2", role: "driver" }));
    if (path.endsWith("/complete")) return Promise.reject(new TypeError("Failed to fetch"));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
  render(<MyWorkPanel membershipId="m2" tenantId="t1" />);
  await screen.findByRole("button", { name: /02.*Corner Shop/ });
  expect(screen.getByText("0 of 2 completed")).toBeInTheDocument();
  browserOnline(false);
  fireEvent.click(screen.getByRole("button", { name: "Mark delivered" }));
  expect(await screen.findByText(/No connection: the completion is saved on this device/)).toBeInTheDocument();
  expect(queueDeliveryCompletion).toHaveBeenCalledWith("t1", "m2", "t1", 1, null);
  expect(screen.getByText("0 of 2 completed")).toBeInTheDocument(); // queued is not delivered
  browserOnline(true);
}

test("a queued completion the server refuses at sync (conflict) is reported and never counted as delivered", async () => {
  await i18n.changeLanguage("en");
  const delivered = { value: false };
  await queueFirstStopOffline(delivered);
  vi.mocked(syncNow).mockResolvedValue(syncResult({ acknowledged: 0, conflicts: 1 }));
  fireEvent.click(screen.getByRole("button", { name: "Sync now" }));
  expect(await screen.findByText("Synced: 0 changes sent, 0 received, 1 conflict.")).toBeInTheDocument();
  expect(syncNow).toHaveBeenCalledWith("t1", "m2");
  expect(screen.getByText("0 of 2 completed")).toBeInTheDocument();
  expect(screen.queryByText("Sent.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /02.*Corner Shop/ })).toBeInTheDocument(); // still an open stop
});

test("a queued completion the server accepts at sync fills the day meter", async () => {
  await i18n.changeLanguage("en");
  const delivered = { value: false };
  await queueFirstStopOffline(delivered);
  vi.mocked(syncNow).mockImplementation(() => { delivered.value = true; return Promise.resolve(syncResult({ acknowledged: 1, conflicts: 0 })); });
  fireEvent.click(screen.getByRole("button", { name: "Sync now" }));
  expect(await screen.findByText("Sent.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("1 of 2 completed")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: /02.*Corner Shop/ })).not.toBeInTheDocument();
});

test("a sync attempted while still offline keeps the completion queued and says so, never 'Sent.'", async () => {
  await i18n.changeLanguage("en");
  await queueFirstStopOffline({ value: false });
  vi.mocked(syncNow).mockResolvedValue({ kind: "offline" });
  fireEvent.click(screen.getByRole("button", { name: "Sync now" }));
  expect(await screen.findByText("No connection. Your changes stay queued on this device.")).toHaveAttribute("role", "status");
  expect(screen.queryByText("Sent.")).not.toBeInTheDocument();
  expect(screen.getAllByText("1 completion waiting to send").length).toBeGreaterThan(0); // still listed: nothing was sent
  expect(screen.getByText("0 of 2 completed")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Sync now" })).toBeEnabled());
});

test("a sync refused because this device lost access clears the local queue and raises an alert", async () => {
  await i18n.changeLanguage("en");
  await queueFirstStopOffline({ value: false });
  vi.mocked(syncNow).mockResolvedValue({ kind: "revoked", reason: "DEVICE_REVOKED" });
  fireEvent.click(screen.getByRole("button", { name: "Sync now" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("This device no longer has access (DEVICE_REVOKED)");
  expect(screen.queryByText("Sent.")).not.toBeInTheDocument();
  expect(screen.getByText("Nothing waiting to send.")).toBeInTheDocument(); // the outbox was set aside on this device
  expect(screen.getByText("0 of 2 completed")).toBeInTheDocument();
});

test("on one pane, a stop's failed or queued completion is shown inside the open stop, which stays open", async () => {
  await i18n.changeLanguage("en");
  onePane();
  let mode: "refused" | "offline" = "refused";
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    if (path.endsWith("/my-work")) return Promise.resolve(Response.json({ tasks: [task, second], membership_id: "m2", role: "driver" }));
    if (path.endsWith("/t2/complete")) {
      return mode === "refused"
        ? Promise.resolve(Response.json({ detail: { code: "VERSION_CONFLICT", message: "This stop changed since it was downloaded." } }, { status: 409 }))
        : Promise.reject(new TypeError("Failed to fetch"));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
  const { container } = render(<MyWorkPanel membershipId="m2" tenantId="t1" />);
  fireEvent.click(await screen.findByRole("button", { name: /03.*Second Stop/ }));
  const panel = screen.getByRole("region", { name: "My route" });
  expect(panel).toHaveClass("show-detail");
  const detail = container.querySelector<HTMLElement>(".stop-detail")!;
  const list = container.querySelector<HTMLElement>(".workspace-list")!;

  fireEvent.click(within(detail).getByRole("button", { name: "Mark delivered" }));
  expect(await within(detail).findByRole("alert")).toHaveTextContent("This stop changed since it was downloaded.");
  expect(panel).toHaveClass("show-detail"); // a failure never closes the stop
  expect(within(list).queryByRole("alert")).not.toBeInTheDocument(); // one copy, where the member is

  browserOnline(false);
  mode = "offline";
  fireEvent.click(within(detail).getByRole("button", { name: "Mark delivered" }));
  expect(await within(detail).findByRole("status")).toHaveTextContent(/No connection: the completion is saved on this device/);
  expect(within(detail).queryByRole("alert")).not.toBeInTheDocument();
  expect(within(list).queryByText(/No connection: the completion is saved/)).not.toBeInTheDocument();
  expect(panel).toHaveClass("show-detail");

  // Back to the list: the result follows the member there; opening another stop starts clean.
  fireEvent.click(within(detail).getByRole("button", { name: "All stops" }));
  expect(panel).not.toHaveClass("show-detail");
  expect(within(list).getByText(/No connection: the completion is saved/)).toHaveAttribute("role", "status");
  fireEvent.click(screen.getByRole("button", { name: /02.*Corner Shop/ }));
  expect(screen.queryByText(/No connection: the completion is saved/)).not.toBeInTheDocument();
});
