import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { AppShell } from "./AppShell";
import { COLLECTION_REPORTS_KEY } from "./collectionReportsApi";
import { PENDING_ORDERS_KEY } from "./pendingOrders";
import { PHONE_PRIMARY_GROUPS, WORKSPACE_SECTIONS, groupOf, ownerSectionHref } from "./workspaceSections";

vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { type: "client", first_name: "Test", last_name: "Owner" }, logout: vi.fn() }) }));
vi.mock("../offline/autoSync", () => ({ useAutoSync: () => ({ pending: 0, attention: 0, sending: false, justSent: false }) }));

const tenantId = "tenant-one";
let client: QueryClient;
function Address() {
  const location = useLocation();
  return <output data-testid="address">{location.pathname}{location.search}</output>;
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
  await i18n.changeLanguage("en");
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
});
afterEach(() => { cleanup(); client?.clear(); });

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
  expect(within(settings).getAllByRole("link").map((row) => row.textContent?.replace(/\u203a/g, ""))).toEqual(["Branding", "Storefront", "Offline sync", "Backup"]);
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

test.each(WORKSPACE_SECTIONS.map(({ id }) => id))("old section=%s highlights its phone group and is reachable within two taps", (id) => {
  shell(id);
  const group = groupOf(id);
  const active = PHONE_PRIMARY_GROUPS.includes(group.id) ? within(phone()).getByRole("link", { name: i18n.t(group.label) }) : more();
  expect(active).toHaveAttribute("aria-current", "page");
  // Every secondary section is a direct row in More. Primary groups need at most a second tap
  // on their section tab (the tabs and actual content are exercised by App.test.tsx).
  if (PHONE_PRIMARY_GROUPS.includes(group.id)) {
    expect(group.sections.length).toBeLessThanOrEqual(3);
    expect(active).toHaveAttribute("href", ownerSectionHref(group.sections[0], tenantId));
  } else {
    fireEvent.click(more());
    const row = within(sheet()).getAllByRole("link").find((link) => link.getAttribute("href") === ownerSectionHref(id, tenantId));
    expect(row).toBeDefined();
    fireEvent.click(row!);
    expect(screen.getByTestId("address")).toHaveTextContent(ownerSectionHref(id, tenantId));
    expect(screen.queryByRole("group", { name: "More options" })).not.toBeInTheDocument();
  }
});
