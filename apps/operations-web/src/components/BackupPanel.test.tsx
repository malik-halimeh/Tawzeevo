import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { PENDING_CONNECT_KEY } from "../backup/connect";
import { BackupPanel } from "./BackupPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });

const tenant = "11111111-1111-4111-8111-111111111111";

test("owner connects Drive with the narrow scope, backs up, verifies and reads the history", async () => {
  await i18n.changeLanguage("en");
  let connected = false;
  const backups: Record<string, unknown>[] = [];
  const restores: Record<string, unknown>[] = [];
  const calls: string[] = [];
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    calls.push(`${init?.method ?? "GET"} ${path}`);
    if (path.includes("/backup/google/authorize")) {
      return Promise.resolve(Response.json({ authorization_url: "https://accounts.google.com/o/oauth2/v2/auth?scope=drive.file&state=s", scope: "https://www.googleapis.com/auth/drive.file" }));
    }
    if (path.includes("/backup/run")) {
      const backup = { id: `backup-${backups.length + 1}`, kind: "MANUAL", status: "UPLOADED", file_name: `tawzeevo-${backups.length + 1}.tzb`, byte_size: 2048, checksum: "abcdef0123456789", manifest: { counts: { customers: 3, invoices: 2 }, migration_version: "20260918_0016", encryption: { algorithm: "AES-256-GCM" } }, error: null, created_at: "2026-09-18T08:00:00Z", completed_at: "2026-09-18T08:00:02Z" };
      backups.unshift(backup);
      return Promise.resolve(Response.json(backup, { status: 201 }));
    }
    if (path.includes("/verify")) {
      const restore = { id: "restore-1", backup_id: "backup-1", mode: "VERIFY", status: "VERIFIED", report: { rows: 5, consistent: true }, created_at: "2026-09-18T08:05:00Z" };
      restores.unshift(restore);
      return Promise.resolve(Response.json(restore));
    }
    if (path.endsWith(`/api/v1/tenants/${tenant}/backup?tenant_id=${tenant}`)) {
      return Promise.resolve(Response.json({
        connection: connected ? { id: "conn-1", provider: "google_drive", account_email: "owner@example.com", folder_name: "Tawzeevo Backup – Route", scopes: "drive.file", connected_at: "2026-09-18T07:00:00Z", last_error: null } : null,
        latest_backup: backups[0] ?? null,
        latest_restore: restores[0] ?? null,
        backups,
        retention: { daily: 30, monthly: 12 },
      }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<BackupPanel tenantId={tenant} />);
  expect(await screen.findByText("Not connected")).toBeInTheDocument();
  expect(screen.getByText("30 daily and 12 monthly backups")).toBeInTheDocument();
  expect(screen.getByText(/drive\.file/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Connect Google Drive" }));
  await waitFor(() => expect(assign).toHaveBeenCalledWith(expect.stringContaining("accounts.google.com")));
  expect(sessionStorage.getItem(PENDING_CONNECT_KEY)).toBe(tenant);

  // Back from Google: the panel now shows the connection and can run a backup.
  connected = true;
  cleanup();
  render(<BackupPanel initialNotice="Google Drive connected as owner@example.com." tenantId={tenant} />);
  expect(await screen.findByText("owner@example.com · folder “Tawzeevo Backup – Route”")).toBeInTheDocument();
  expect(screen.getByText("Google Drive connected as owner@example.com.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Back up now" }));
  expect(await screen.findByText("Backup uploaded: tawzeevo-1.tzb")).toBeInTheDocument();
  expect(await screen.findByText(/5 rows · sha256 abcdef012345/)).toBeInTheDocument();
  expect(screen.getByText("Stored")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run restore drill" }));
  expect(await screen.findByText("Restore drill passed: 5 rows decrypted and reconciled with the manifest.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/verified$/)).toBeInTheDocument());
  // The panel never asks for or displays keys or tokens.
  expect(calls.some((call) => call.includes("token") || call.includes("key"))).toBe(false);
});
