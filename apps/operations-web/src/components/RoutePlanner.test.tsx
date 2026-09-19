import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { RoutePlanner } from "./RoutePlanner";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("suggests a labelled offline stop order, lets the owner reorder by hand and saves it", async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("navigator", { ...navigator, geolocation: undefined });
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = (input instanceof Request ? input.url : input.toString()).split("?")[0]!;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined;
    if (body) bodies.push(body);
    if (path.endsWith("/routes/suggest-order")) return Promise.resolve(Response.json({ method: "offline stop-order suggestion", note: null, stops: [{ task_id: "b", sequence: 1, customer_name: "Near", latitude: "1", longitude: "1", has_location: true }, { task_id: "a", sequence: 2, customer_name: "Far", latitude: "2", longitude: "2", has_location: true }, { task_id: "c", sequence: 3, customer_name: "Nowhere", latitude: null, longitude: null, has_location: false }], unlocated_task_ids: ["c"] }));
    if (path.endsWith("/routes/order")) return Promise.resolve(Response.json({ tasks: [], membership_id: "m", role: "owner" }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<RoutePlanner tasks={[{ id: "a", customer_name: "Far", version: 1 }, { id: "b", customer_name: "Near", version: 1 }, { id: "c", customer_name: "Nowhere", version: 1 }]} tenantId="t1" />);
  fireEvent.click(screen.getByRole("button", { name: "Suggest stop order" }));
  expect(await screen.findByText("Offline stop-order suggestion")).toBeInTheDocument();
  expect(screen.getByText(/a suggestion, not a guaranteed best road route/)).toBeInTheDocument();
  expect(screen.getByText(/no saved location, put last/)).toBeInTheDocument();
  expect(bodies[0]).toEqual({ origin: null, task_ids: ["a", "b", "c"] });
  fireEvent.click(screen.getByRole("button", { name: "Move Far up" }));
  fireEvent.click(screen.getByRole("button", { name: "Save this order" }));
  expect(await screen.findByText("Stop order saved.")).toBeInTheDocument();
  expect(bodies[1]).toEqual({ task_ids: ["a", "b", "c"] });
});
