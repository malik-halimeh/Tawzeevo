import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { apiRequest } from "../../api/client";
import i18n from "../../i18n";
import { sectionHref } from "../workspaceSections";
import { SettingsHub } from "./SettingsHub";

vi.mock("../../api/client", async (original) => ({ ...await original<typeof import("../../api/client")>(), apiRequest: vi.fn() }));

const tenantId = "business-one";
const signOut = vi.fn();
const chooseBusiness = vi.fn();
let client: QueryClient;
let storefront: { slug?: string };
let threshold: number | null;
let latestBackup: { completed_at: string | null } | null;

function Page({ several }: { several: boolean }) {
  const [search] = useSearchParams();
  const location = useLocation();
  return <><output data-testid="address">{location.pathname}{location.search}</output>{search.get("section") === "settings" ? <SettingsHub tenantId={search.get("tenant")!} tenantParam={search.get("tenant")} businessName="Example business" onChooseBusiness={several ? chooseBusiness : undefined} /> : null}</>;
}

function hub(view?: string, { several = false, syncText = "All sent" }: { several?: boolean; syncText?: string } = {}) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[sectionHref("settings", tenantId, { view: view ?? null })]}><Routes><Route element={<Outlet context={{ syncText, signOut }} />}><Route path="/workspace" element={<Page several={several} />} /><Route path="/profile" element={<Page several={false} />} /><Route path="/stats" element={<Page several={false} />} /></Route></Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(async () => {
  vi.clearAllMocks();
  storefront = { slug: "example-shop" };
  threshold = 21;
  latestBackup = { completed_at: "2026-10-28T08:30:00Z" };
  await i18n.changeLanguage("en");
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
  vi.mocked(apiRequest).mockImplementation((path) => {
    if (path.includes("/storefront?")) return Promise.resolve(storefront);
    if (path.includes("/customer-ledger/settings?")) return Promise.resolve({ customer_overdue_threshold_days: threshold });
    if (path.includes("/backup?")) return Promise.resolve({ latest_backup: latestBackup });
    return Promise.reject(new Error(`Unexpected request: ${path}`));
  });
});
afterEach(() => { cleanup(); client?.clear(); });

test.each([undefined, "unknown", "business"])("Business is the default for view=%s, with existing values and no business picker for one business", async (view) => {
  hub(view);
  expect(screen.getByRole("heading", { name: "Business" })).toBeInTheDocument();
  const rows = screen.getByRole("list", { name: "Business" });
  expect(within(rows).getByRole("link", { name: "Branding, Example business" })).toHaveAttribute("href", sectionHref("branding", tenantId));
  expect(await within(rows).findByRole("link", { name: "Storefront & campaigns, example-shop" })).toHaveAttribute("href", sectionHref("storefront", tenantId));
  expect(within(rows).queryByRole("button", { name: "Business" })).not.toBeInTheDocument();
  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /actions/i })).not.toBeInTheDocument();
  expect(apiRequest).toHaveBeenCalledTimes(1);
  expect(apiRequest).toHaveBeenCalledWith(`/api/v1/tenants/${tenantId}/storefront?tenant_id=${tenantId}`);
});

test("several businesses expose the existing picker action", () => {
  hub("business", { several: true });
  fireEvent.click(screen.getByRole("button", { name: "Business" }));
  expect(chooseBusiness).toHaveBeenCalledOnce();
});

test.each([
  ["business", "Branding, Example business", "branding", undefined],
  ["business", "Storefront & campaigns", "storefront", undefined],
  ["invoices", "Customer grade discounts", "pricing", undefined],
  ["invoices", "Overdue after (days)", "invoices", "balances"],
  ["invoices", "Opening balances", "invoices", "balances"],
  ["general", "Offline sync, All sent", "sync", undefined],
  ["general", "Backup", "backup", undefined],
] as const)("%s row %s opens its existing address", (page, label, section, view) => {
  hub(page);
  const link = screen.getByRole("link", { name: label });
  const href = sectionHref(section, tenantId, { view: view ?? null });
  expect(link).toHaveAttribute("href", href);
  fireEvent.click(link);
  expect(screen.getByTestId("address").textContent).toBe(href);
});

test("Invoices & pricing reads only financial settings and keeps sharing as a note", async () => {
  hub("invoices");
  expect(await screen.findByRole("link", { name: "Overdue after (days), 21" })).toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent("Sharing links are created on a confirmed invoice.");
  expect(screen.queryByRole("link", { name: /Invoice sharing/ })).not.toBeInTheDocument();
  expect(apiRequest).toHaveBeenCalledTimes(1);
  expect(apiRequest).toHaveBeenCalledWith(`/api/v1/customer-ledger/settings?tenant_id=${tenantId}`);
});

test.each([null, 0])("overdue threshold %s is absent only when missing", async (value) => {
  threshold = value;
  hub("invoices");
  await waitFor(() => expect(client.isFetching()).toBe(0));
  const label = value === null ? "Overdue after (days)" : "Overdue after (days), 0";
  await waitFor(() => expect(screen.getByRole("link", { name: label })).toHaveAccessibleName(label));
});

test("Business omits the storefront value when its existing response has no slug", async () => {
  storefront = {};
  hub("business");
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(screen.getByRole("link", { name: "Storefront & campaigns" })).toHaveAccessibleName("Storefront & campaigns");
});

test("General shows current language, the shell sync text and last backup; language switches exactly like the shell", async () => {
  hub("general", { syncText: "3 changes waiting" });
  expect(screen.getByRole("link", { name: "Offline sync, 3 changes waiting" })).toBeInTheDocument();
  const date = new Date(latestBackup!.completed_at!).toLocaleString("en-GB");
  expect(await screen.findByRole("link", { name: `Backup, ${date}` })).toBeInTheDocument();
  expect(apiRequest).toHaveBeenCalledTimes(1);
  expect(apiRequest).toHaveBeenCalledWith(`/api/v1/tenants/${tenantId}/backup?tenant_id=${tenantId}`);
  fireEvent.click(screen.getByRole("button", { name: "Language, English" }));
  await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
  expect(document.documentElement.lang).toBe("ar");
  fireEvent.click(screen.getByRole("button", { name: `${i18n.t("nav.language")}, ${i18n.t("nav.currentLanguage")}` }));
  await waitFor(() => expect(document.documentElement.dir).toBe("ltr"));
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(signOut).toHaveBeenCalledOnce();
});

test.each(["Profile", "Public statistics"])("General opens the existing %s route", (title) => {
  hub("general");
  const path = title === "Profile" ? "/profile" : "/stats";
  const link = screen.getByRole("link", { name: title });
  expect(link).toHaveAttribute("href", path);
  fireEvent.click(link);
  expect(screen.getByTestId("address").textContent).toBe(path);
});

test.each([null, { completed_at: null }])("General omits an unavailable backup date (%s)", async (backup) => {
  latestBackup = backup;
  hub("general");
  await waitFor(() => expect(client.isFetching()).toBe(0));
  expect(screen.getByRole("link", { name: "Backup" })).toHaveAccessibleName("Backup");
  expect(screen.queryByText(/Never|Invalid Date/)).not.toBeInTheDocument();
});

test.each(["business", "invoices", "general"])("unavailable summary data leaves %s rows usable without invented values", async (page) => {
  vi.mocked(apiRequest).mockRejectedValue(new Error("Offline"));
  hub(page);
  await waitFor(() => expect(client.isFetching()).toBe(0));
  const title = page === "business" ? "Storefront & campaigns" : page === "invoices" ? "Overdue after (days)" : "Backup";
  expect(screen.getByRole("link", { name: title })).toHaveAccessibleName(title);
});

test.each(["business", "invoices", "general"])("%s renders translated rows and the selected page in Arabic/RTL", async (page) => {
  await i18n.changeLanguage("ar");
  document.documentElement.lang = "ar";
  document.documentElement.dir = "rtl";
  hub(page);
  expect(screen.getByRole("heading", { name: i18n.t(`settingsHub.${page}`) })).toBeInTheDocument();
  const pages = screen.getByRole("navigation", { name: i18n.t("settingsHub.pages") });
  expect(within(pages).getByRole("link", { name: i18n.t(`settingsHub.${page}`) })).toHaveAttribute("aria-current", "page");
  for (const link of screen.getAllByRole("link")) expect(link).toHaveAccessibleName();
  expect(document.documentElement.dir).toBe("rtl");
});
