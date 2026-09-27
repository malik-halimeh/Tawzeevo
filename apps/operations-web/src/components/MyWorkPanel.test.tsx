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

test("after a delivery the next stop opens, Navigate hands off to Google Maps, and re-planning starts from the delivered customer", async () => {
  await i18n.changeLanguage("en");
  const second = { ...task, id: "t2", customer_name: "Byblos Shop", customer_latitude: "34.121100", customer_longitude: "35.648100", route_sequence: 3 };
  const third = { ...task, id: "t3", customer_name: "Tyre Shop", customer_latitude: "33.273300", customer_longitude: "35.203600", route_sequence: 4 };
  const calls: { path: string; body?: Record<string, unknown> }[] = [];
  let remaining = [task, second, third];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    calls.push({ path, ...(typeof init?.body === "string" ? { body: JSON.parse(init.body) as Record<string, unknown> } : {}) });
    if (path.endsWith("/my-work")) return Promise.resolve(Response.json({ tasks: remaining, membership_id: "m2", role: "driver" }));
    if (path.endsWith("/t1/complete")) { remaining = [second, third]; return Promise.resolve(Response.json({ ...task, status: "COMPLETED", version: 2 })); }
    if (path.endsWith("/routes/path")) return Promise.resolve(Response.json({ method: "straight-line", points: [] }));
    if (path.endsWith("/routes/suggest-order")) return Promise.resolve(Response.json({ method: "openrouteservice", note: null, stops: [{ task_id: "t3" }, { task_id: "t2" }], unlocated_task_ids: [] }));
    if (path.endsWith("/routes/order")) { remaining = [{ ...third, route_sequence: 1 }, { ...second, route_sequence: 2 }]; return Promise.resolve(Response.json({ tasks: remaining, membership_id: "m2", role: "driver" })); }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<MyWorkPanel membershipId="m2" tenantId="t1" />);
  expect(await screen.findByRole("heading", { name: "Corner Shop" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Map of the stops" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Navigate" })).toHaveAttribute("href", "https://www.google.com/maps/dir/?api=1&destination=33.895000,35.478000&travelmode=driving");

  fireEvent.click(screen.getByRole("button", { name: "Mark delivered" }));
  expect(await screen.findByText("Marked delivered. Next stop: Byblos Shop")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Byblos Shop" })).toBeInTheDocument(); // the next stop opened by itself
  expect(calls.some((call) => call.path.endsWith("/routes/suggest-order"))).toBe(false); // never re-planned without asking

  fireEvent.click(screen.getByRole("button", { name: "Re-plan the rest from Corner Shop" }));
  expect(await screen.findByText("Remaining stops re-planned from Corner Shop and saved.")).toBeInTheDocument();
  expect(calls.find((call) => call.path.endsWith("/routes/suggest-order"))?.body).toEqual({ origin: { latitude: "33.895000", longitude: "35.478000" }, task_ids: ["t2", "t3"] });
  expect(calls.find((call) => call.path.endsWith("/routes/order"))?.body).toEqual({ task_ids: ["t3", "t2"] });
  expect(screen.getByRole("heading", { name: "Tyre Shop" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Re-plan the rest/ })).not.toBeInTheDocument();
});

test("Directions reads the position once and shows the road route, distance, time and turns inside the app", async () => {
  await i18n.changeLanguage("en");
  const getCurrentPosition = vi.fn((success: PositionCallback) => success({ coords: { latitude: 33.8886, longitude: 35.5157, accuracy: 10 } } as GeolocationPosition));
  vi.stubGlobal("navigator", { ...navigator, geolocation: { getCurrentPosition, watchPosition: vi.fn() } });
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    if (path.endsWith("/my-work")) return Promise.resolve(Response.json({ tasks: [task], membership_id: "m2", role: "driver" }));
    if (path.endsWith("/routes/directions")) {
      bodies.push(JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>);
      return Promise.resolve(Response.json({ method: "openrouteservice", distance_m: 17445.8, duration_s: 992.5, points: [[33.8886, 35.5157], [33.895, 35.478]], steps: [{ type: 11, name: null, distance_m: 38.6, duration_s: 6.9, exit_number: null }, { type: 1, name: "Charles Helou", distance_m: 3276, duration_s: 143, exit_number: null }, { type: 10, name: null, distance_m: 0, duration_s: 0, exit_number: null }] }));
    }
    return Promise.resolve(Response.json({ method: "straight-line", points: [] }));
  }));

  render(<MyWorkPanel membershipId="m2" tenantId="t1" />);
  fireEvent.click(await screen.findByRole("button", { name: "Directions" }));
  const panel = await screen.findByRole("region", { name: "Directions to Corner Shop" });
  expect(bodies).toEqual([{ origin: { latitude: "33.888600", longitude: "35.515700" }, task_id: "t1" }]);
  expect(getCurrentPosition).toHaveBeenCalledTimes(1);
  expect(within(panel).getByText("17 km")).toBeInTheDocument();
  expect(within(panel).getByText(/about 17 min by car/)).toBeInTheDocument();
  expect(within(panel).getByRole("region", { name: "Map of the directions" })).toBeInTheDocument();
  expect(within(panel).getAllByRole("listitem").map((item) => item.textContent)).toEqual(["Head outthen 40 m", "Turn right onto \u2068Charles Helou\u2069then 3.3 km", "Arrive at Corner Shop"]);
  fireEvent.click(within(panel).getByRole("button", { name: "Hide directions" }));
  expect(screen.queryByRole("region", { name: "Directions to Corner Shop" })).not.toBeInTheDocument();
});
