import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { AppShell } from "./AppShell";
import { SettingsHub } from "./settings/SettingsHub";
import { useAutoSync } from "../offline/autoSync";
import { COLLECTION_REPORTS_KEY } from "./collectionReportsApi";
import { PENDING_ORDERS_KEY } from "./pendingOrders";
import { PHONE_PRIMARY_GROUPS, WORKSPACE_SECTIONS, groupOf, ownerSectionHref, sectionHref } from "./workspaceSections";

vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { type: "client", first_name: "Test", last_name: "Owner" }, logout: vi.fn() }) }));
vi.mock("../offline/autoSync", () => ({ useAutoSync: vi.fn() }));

const tenantId = "tenant-one";
let client: QueryClient;
function Address() {
  const location = useLocation();
  const [search] = useSearchParams();
  return <><output data-testid="address">{location.pathname}{location.search}</output>{search.get("section") === "settings" ? <SettingsHub tenantId={tenantId} tenantParam={tenantId} businessName="Example" /> : null}</>;
}
function shell(section = "invoices", badge = false) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["tenant-contexts"], { tenants: [{ tenant_id: tenantId, membership_id: "member-one", tenant_name: "Example", role: "owner", tenant_status: "ACTIVE" }] });
  client.setQueryData([PENDING_ORDERS_KEY, tenantId], badge ? [{ id: "order-one" }, { id: "order-two" }] : []);
  client.setQueryData([COLLECTION_REPORTS_KEY, tenantId], badge ? [{ id: "report-one" }] : []);
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/workspace?tenant=${tenantId}&section=${section}`]}><Routes><Route element={<AppShell />}><Route path="/workspace" element={<Address />} /></Route></Routes></MemoryRouter></QueryClientProvider>);
}
const phone = () => screen.getByRole("navigation", { name: i18n.t("nav.primary") });
const more = () => within(phone()).getByRole("button", { name: i18n.t("nav.more") });
const sheet = () => screen.getByRole("group", { name: i18n.t("nav.moreMenu") });

beforeEach(async () => {
  vi.mocked(useAutoSync).mockReturnValue({ pending: 0, attention: 0, sending: false, justSent: false, online: true });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({})));
  await i18n.changeLanguage("en");
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
});
afterEach(() => { cleanup(); client?.clear(); vi.unstubAllGlobals(); });

test.each(["en", "ar"])("owner phone has exactly five named slots in %s", async (language) => {
  await i18n.changeLanguage(language);
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  shell();
  const slots = [...within(phone()).getAllByRole("link"), ...within(phone()).getAllByRole("button")];
  expect(slots).toHaveLength(5);
  expect(slots.map((slot) => slot.textContent)).toEqual([i18n.t("nav.groups.today"), i18n.t("nav.groups.sales"), i18n.t("nav.groups.customers"), i18n.t("nav.groups.catalog"), i18n.t("nav.more")]);
  for (const slot of slots) expect(slot).toHaveAccessibleName();
});

test("the Sales slot keeps both waiting-order and collection counts", () => {
  shell("orders", true);
  const sales = within(phone()).getByRole("link", { name: /^Sales/ });
  expect(sales).toHaveAttribute("href", ownerSectionHref("invoices", tenantId));
  expect(sales).toHaveAttribute("aria-current", "page");
  expect(sales.querySelector(".nav-badge > span[aria-hidden]")).toHaveTextContent("3");
  expect(sales).toHaveAccessibleName(/2 awaiting review/);
  expect(sales).toHaveAccessibleName(new RegExp(i18n.t("collection.badge", { count: 1 })));
});

test("More offers grouped direct rows, the current language, and Escape/close focus return", async () => {
  shell("suppliers");
  expect(more()).toHaveAttribute("aria-current", "page");
  fireEvent.click(more());
  const tools = within(sheet()).getByRole("group", { name: "Work tools" });
  expect(within(tools).getAllByRole("link")).toHaveLength(5);
  const settings = within(sheet()).getByRole("group", { name: "Settings" });
  expect(within(settings).getAllByRole("link").map((row) => row.textContent?.replace(/\u203a/g, ""))).toEqual(["Business", "Invoices & pricing", "General"]);
  expect(within(settings).getAllByRole("link").map((row) => row.getAttribute("href"))).toEqual(["business", "invoices", "general"].map((view) => sectionHref("settings", tenantId, { view })));
  const account = within(sheet()).getByRole("group", { name: "Account" });
  expect(within(account).getByRole("link", { name: "Profile" })).toHaveAttribute("href", "/profile");
  expect(within(account).getByRole("link", { name: "Public statistics" })).toHaveAttribute("href", "/stats");
  expect(within(account).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  for (const row of [...within(sheet()).getAllByRole("link"), ...within(sheet()).getAllByRole("button")]) expect(row).toHaveAccessibleName();
  expect(within(tools).getAllByRole("link")[0]).toHaveFocus();
  fireEvent.click(within(account).getByRole("button", { name: "Language: English" }));
  await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
  expect(document.documentElement.lang).toBe("ar");
  const arabic = within(sheet()).getByRole("button", { name: `${i18n.t("nav.language")}: ${i18n.t("nav.currentLanguage")}` });
  expect(arabic).toHaveTextContent("العربية");
  fireEvent.click(arabic);
  await waitFor(() => expect(document.documentElement.dir).toBe("ltr"));
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("group", { name: "More options" })).not.toBeInTheDocument();
  expect(more()).toHaveFocus();
  fireEvent.click(more());
  fireEvent.click(within(sheet()).getByRole("button", { name: "Close menu" }));
  expect(more()).toHaveFocus();
  expect(more()).toHaveAttribute("aria-expanded", "false");
});

test("Arabic Work tools omit repeated sub-labels and keep distinct group labels", async () => {
  await i18n.changeLanguage("ar");
  document.documentElement.lang = "ar";
  document.documentElement.dir = "rtl";
  shell();
  fireEvent.click(more());
  const tools = within(sheet()).getByRole("group", { name: i18n.t("nav.workTools") });
  for (const id of ["procurement", "analytics", "suppliers", "assistant"] as const) {
    const meta = WORKSPACE_SECTIONS.find((item) => item.id === id)!;
    const title = i18n.t(meta.label);
    const groupLabel = i18n.t(groupOf(id).label);
    const row = within(tools).getByRole("link", { name: id === "procurement" || id === "analytics" ? title : `${title}, ${groupLabel}` });
    expect(within(row).getAllByText(title, { exact: true })).toHaveLength(1);
    if (id === "procurement" || id === "analytics") {
      expect(row.querySelector("small")).toBeNull();
    } else {
      expect(row.querySelector("small")).toHaveTextContent(groupLabel);
    }
  }
});

test.each(WORKSPACE_SECTIONS.map(({ id }) => id))("section=%s highlights its phone group: daily/tools ≤2 taps; settings ≤3 through the hub (Q6)", (id) => {
  shell(id);
  const group = groupOf(id);
  const active = PHONE_PRIMARY_GROUPS.includes(group.id) ? within(phone()).getByRole("link", { name: i18n.t(group.label) }) : more();
  expect(active).toHaveAttribute("aria-current", "page");
  // Settings intentionally take More → hub page → row (Q6); daily sections and tools keep ≤2 taps.
  // Primary groups need at most a second tap on their section tab (App.test.tsx covers content).
  if (PHONE_PRIMARY_GROUPS.includes(group.id)) {
    expect(group.sections.length).toBeLessThanOrEqual(3);
    expect(active).toHaveAttribute("href", ownerSectionHref(group.sections[0], tenantId));
  } else if (group.id === "settings") {
    fireEvent.click(more()); // tap 1
    const page = id === "sync" || id === "backup" ? "general" : "business";
    const row = within(sheet()).getAllByRole("link").find((link) => link.getAttribute("href") === sectionHref("settings", tenantId, { view: page }));
    expect(row).toBeDefined();
    fireEvent.click(row!); // tap 2
    expect(screen.getByTestId("address")).toHaveTextContent(sectionHref("settings", tenantId, { view: page }));
    if (id !== "settings") {
      const destination = screen.getAllByRole("link").find((link) => link.getAttribute("href") === ownerSectionHref(id, tenantId));
      expect(destination).toBeDefined();
      fireEvent.click(destination!); // tap 3
      expect(screen.getByTestId("address").textContent).toBe(ownerSectionHref(id, tenantId));
    }
    expect(screen.queryByRole("group", { name: "More options" })).not.toBeInTheDocument();
  } else {
    fireEvent.click(more());
    const row = within(sheet()).getAllByRole("link").find((link) => link.getAttribute("href") === ownerSectionHref(id, tenantId));
    expect(row).toBeDefined();
    fireEvent.click(row!);
    expect(screen.getByTestId("address")).toHaveTextContent(ownerSectionHref(id, tenantId));
    expect(screen.queryByRole("group", { name: "More options" })).not.toBeInTheDocument();
  }
});

test.each([
  { pending: 0, attention: 0, sending: false, justSent: false },
  { pending: 0, attention: 0, sending: false, justSent: true },
  { pending: 3, attention: 0, sending: false, justSent: false },
  { pending: 3, attention: 0, sending: true, justSent: false },
  { pending: 0, attention: 2, sending: false, justSent: false },
])("General reuses the chip's exact state text: %s", (state) => {
  vi.mocked(useAutoSync).mockReturnValue({ ...state, online: true });
  shell("settings&view=general");
  const chip = document.querySelector(".topline-actions .online")!;
  const full = chip.querySelector(".sync-full")!.textContent;
  expect(chip).toHaveAttribute("aria-label", full);
  expect(chip).toHaveAttribute("title", full);
  expect(screen.getByRole("link", { name: `Offline sync, ${full}` })).toBeInTheDocument();
});

test.each([0, 3])("General also reuses the chip's browser-offline text with %s changes", (pending) => {
  vi.mocked(useAutoSync).mockReturnValue({ pending, attention: 0, sending: false, justSent: false, online: false });
  shell("settings&view=general");
  fireEvent(window, new Event("offline"));
  const chip = document.querySelector(".topline-actions .online")!;
  expect(chip).toHaveAttribute("data-state", "offline");
  const full = chip.querySelector(".sync-full")!.textContent;
  expect(chip).toHaveAttribute("aria-label", full);
  expect(chip).toHaveAttribute("title", full);
  expect(screen.getByRole("link", { name: `Offline sync, ${full}` })).toBeInTheDocument();
});

test.each(["en", "ar"])("short connection words keep the full accessible description in %s", async (language) => {
  await i18n.changeLanguage(language);
  shell();
  const chip = document.querySelector(".topline-actions .online")!;
  expect(chip.querySelector(".sync-short")).toHaveTextContent(i18n.t("shell.short.online"));
  expect(chip.querySelector(".sync-short")).toHaveAttribute("aria-hidden", "true");
  expect(chip).toHaveAttribute("aria-label", i18n.t("shell.browserOnline"));
  expect(chip).toHaveAttribute("title", i18n.t("shell.browserOnline"));
  fireEvent(window, new Event("offline"));
  expect(chip.querySelector(".sync-short")).toHaveTextContent(i18n.t("shell.short.offline"));
  expect(chip).toHaveAttribute("aria-label", i18n.t("shell.browserOffline"));
});

test.each(["en", "ar"])("sending and attention have short words and preserve their status/link in %s", async (language) => {
  await i18n.changeLanguage(language);
  vi.mocked(useAutoSync).mockReturnValue({ pending: 3, attention: 0, sending: true, justSent: false, online: true });
  shell();
  expect(screen.getByRole("status", { name: i18n.t("shell.sending") })).toHaveTextContent(i18n.t("shell.short.sending"));
  cleanup(); client.clear();
  vi.mocked(useAutoSync).mockReturnValue({ pending: 0, attention: 2, sending: false, justSent: false, online: true });
  shell();
  const attention = screen.getByRole("link", { name: i18n.t("shell.syncAttention", { count: 2 }) });
  expect(attention).toHaveTextContent(i18n.t("shell.short.attention"));
  expect(attention).toHaveAttribute("href", sectionHref("sync", tenantId));
});

test.each(["", "&view=unknown", "&view=business", "&view=invoices", "&view=general"])("More agrees with the hub's selected page for settings%s", (query) => {
  shell(`settings${query}`);
  const title = screen.getByRole("heading").textContent;
  fireEvent.click(more());
  const settings = within(sheet()).getByRole("group", { name: "Settings" });
  expect(within(settings).getByRole("link", { name: title })).toHaveAttribute("aria-current", "page");
});
