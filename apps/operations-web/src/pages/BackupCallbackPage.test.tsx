import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import "../i18n";
import { BackupCallbackPage } from "./BackupCallbackPage";

vi.mock("../backup/connect", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../backup/connect")>();
  return { ...actual, completeGoogleConnect: vi.fn(() => Promise.resolve({ id: "c1", provider: "google", account_email: "owner@example.com", folder_name: "Tawzeevo", scopes: "", connected_at: "2026-09-27T00:00:00Z", last_error: null })) };
});

let address = "";
function AddressProbe() {
  const location = useLocation();
  address = `${location.pathname}${location.search}`;
  return null;
}

afterEach(() => { cleanup(); sessionStorage.clear(); address = ""; });

test("returns to the Backup section of the business that was being connected", async () => {
  sessionStorage.setItem("tawzeevo.backup.connect.tenant", "tenant-b");
  render(
    <MemoryRouter initialEntries={["/backup/google/callback?code=abc&state=xyz"]}>
      <Routes>
        <Route element={<BackupCallbackPage />} path="/backup/google/callback" />
        <Route element={<AddressProbe />} path="/workspace" />
      </Routes>
    </MemoryRouter>,
  );
  await waitFor(() => expect(address).toBe("/workspace?tenant=tenant-b&section=backup"));
  expect(JSON.parse(sessionStorage.getItem("tawzeevo.backup.connect.result") ?? "{}")).toEqual({ tenant_id: "tenant-b", email: "owner@example.com" });
});
