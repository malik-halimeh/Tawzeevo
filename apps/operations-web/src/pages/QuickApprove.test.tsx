import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { TenantApplication } from "../api/types";
import i18n from "../i18n";
import { QuickApprove } from "./QuickApprove";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

test("Approve (30 days) sends the existing approve call with today plus 30 days and no grace (D-110)", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 8, 27, 23, 30)); // late evening, local calendar date 27 Sept
  const bodies: Array<{ path: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    bodies.push({ path, body: typeof init?.body === "string" ? JSON.parse(init.body) : null });
    return Promise.resolve(Response.json({ id: "a1", business_name: "Hamra Foods", status: "APPROVED" }));
  }));
  const application = { id: "a1", business_name: "Hamra Foods", status: "PENDING" } as TenantApplication;
  const done = vi.fn();
  render(<QueryClientProvider client={new QueryClient()}><QuickApprove application={application} onDone={done} /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Approve \(30 days\)/ }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(bodies).toEqual([{ path: "/api/v1/platform/tenant-applications/a1/approve", body: { access_until: "2026-10-27", grace_until: null, review_notes: null } }]);
});
