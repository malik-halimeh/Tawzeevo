import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { PhoneNotifications } from "./PhoneNotifications";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function browser({ permission = "default", existing = null as null | { endpoint: string } } = {}) {
  const requestPermission = vi.fn(() => Promise.resolve("granted"));
  const subscription = { endpoint: "https://push.example.test/1", toJSON: () => ({ endpoint: "https://push.example.test/1", keys: { p256dh: "k", auth: "a" } }), unsubscribe: vi.fn(() => Promise.resolve(true)) };
  const pushManager = { getSubscription: vi.fn(() => Promise.resolve(existing ? subscription : null)), subscribe: vi.fn(() => Promise.resolve(subscription)) };
  const registration = { pushManager };
  vi.stubGlobal("Notification", Object.assign(function Notification() { /* stub */ }, { permission, requestPermission }));
  vi.stubGlobal("PushManager", function PushManager() { /* stub */ });
  vi.stubGlobal("navigator", { ...navigator, serviceWorker: { getRegistration: vi.fn(() => Promise.resolve(registration)), ready: Promise.resolve(registration) } });
  return { requestPermission, pushManager, subscription };
}

function server(enabled: boolean, subscribed = false) {
  const writes: Array<{ method: string; path: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    const method = init?.method ?? "GET";
    if (path === "/api/v1/push/public-key") return Promise.resolve(Response.json({ enabled, public_key: enabled ? "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U" : null }));
    if (path === "/api/v1/push/subscriptions/state") return Promise.resolve(Response.json({ subscribed }));
    writes.push({ method, path, body: typeof init?.body === "string" ? JSON.parse(init.body) : null });
    return Promise.resolve(new Response(null, { status: 204 }));
  }));
  return writes;
}

test("permission is asked only on Turn on, then this browser is subscribed (D-116)", async () => {
  const { requestPermission, pushManager } = browser();
  const writes = server(true);
  render(<PhoneNotifications />);
  expect(await screen.findByText("Off for this device.")).toBeInTheDocument();
  expect(requestPermission).not.toHaveBeenCalled();
  expect(screen.getByText(/On iPhone/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Turn on" }));
  expect(await screen.findByText("On for this device.")).toBeInTheDocument();
  expect(requestPermission).toHaveBeenCalledTimes(1);
  expect(pushManager.subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }));
  expect(writes).toEqual([{ method: "POST", path: "/api/v1/push/subscriptions", body: { endpoint: "https://push.example.test/1", keys: { p256dh: "k", auth: "a" } } }]);
});

test("on turns off; blocked, unsupported and unavailable each say so", async () => {
  const { subscription } = browser({ existing: { endpoint: "x" } });
  let writes = server(true, true);
  render(<PhoneNotifications />);
  fireEvent.click(await screen.findByRole("button", { name: "Turn off" }));
  expect(await screen.findByText("Off for this device.")).toBeInTheDocument();
  expect(writes).toEqual([{ method: "DELETE", path: "/api/v1/push/subscriptions", body: { endpoint: "https://push.example.test/1" } }]);
  expect(subscription.unsubscribe).toHaveBeenCalled();
  cleanup();

  browser({ permission: "denied" });
  writes = server(true);
  render(<PhoneNotifications />);
  expect(await screen.findByText(/blocked for this site/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Turn on" })).not.toBeInTheDocument();
  cleanup();

  browser();
  server(false);
  render(<PhoneNotifications />);
  expect(await screen.findByText("Phone notifications are not available yet.")).toBeInTheDocument();
  cleanup();

  vi.unstubAllGlobals();
  vi.stubGlobal("navigator", { ...navigator, serviceWorker: undefined });
  server(true);
  render(<PhoneNotifications />);
  await waitFor(() => expect(screen.getByText("This browser cannot show phone notifications.")).toBeInTheDocument());
  expect(writes).toEqual([]);
});
