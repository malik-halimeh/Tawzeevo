import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { AnalyticsPanel } from "./AnalyticsPanel";
import { CopilotPanel } from "./CopilotPanel";
import { DeliveryPanel } from "./DeliveryPanel";
import { ProcurementPanel } from "./ProcurementPanel";
import { SupplierSetup } from "./SupplierSetup";

afterEach(async () => { cleanup(); vi.unstubAllGlobals(); await i18n.changeLanguage("en"); });

const pages = [
  { Panel: DeliveryPanel, title: "delivery.titleSole", eyebrow: "delivery.kicker", body: "delivery.bodySole" },
  { Panel: ProcurementPanel, title: "procurement.title", eyebrow: "procurement.kicker", body: "procurement.body" },
  { Panel: SupplierSetup, title: "supplierSetup.title", eyebrow: "supplierSetup.kicker", body: "supplierSetup.body" },
  { Panel: AnalyticsPanel, title: "analytics.title", eyebrow: "analytics.kicker", body: "analytics.body" },
  { Panel: CopilotPanel, title: "copilot.title", eyebrow: "copilot.kicker", body: "copilot.body" },
];

const countedPages = [
  { Panel: DeliveryPanel, title: "delivery.titleSole", en: "0 deliveries", ar: "لا توصيلات" },
  { Panel: ProcurementPanel, title: "procurement.title", en: "0 lists", ar: "لا قوائم" },
  { Panel: SupplierSetup, title: "supplierSetup.title", en: "0 suppliers", ar: "لا مورّدين" },
];

for (const language of ["en", "ar"]) {
  test.each(pages)(`${language}: $title keeps its title, eyebrow and description without inventing controls or a loading count`, async ({ Panel, title, eyebrow, body }) => {
    await i18n.changeLanguage(language);
    // Hold the real panel requests so an unloaded list cannot masquerade as an empty list.
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter><div dir={i18n.dir()}><Panel tenantId="header-test" /></div></MemoryRouter></QueryClientProvider>);
    const page = screen.getByRole("region", { name: i18n.t(title) });
    const heading = within(page).getByRole("heading", { level: 1, name: i18n.t(title) });
    const header = heading.closest("header")!;
    expect(header).toHaveClass("page-head", "list-head");
    expect(within(header).getByText(i18n.t(eyebrow))).toBeVisible();
    expect(within(header).queryByRole("button")).not.toBeInTheDocument();
    expect(within(header).queryByRole("searchbox")).not.toBeInTheDocument();
    expect(header.querySelector(".list-head-count")).toBeNull();
    expect(within(page).getByText(i18n.t(body))).toBeVisible();
    view.unmount();
    client.clear();
  });

  test.each(countedPages)(`${language}: $title names the records in its loaded count`, async ({ Panel, title, en, ar }) => {
    await i18n.changeLanguage(language);
    const answers: Record<string, unknown> = {
      "/api/v1/delivery-tasks": { tasks: [], eligible_members: [], sole_operator: true },
      "/api/v1/delivery-tasks/eligible-invoices": { invoices: [] },
      "/api/v1/tenants/header-test/memberships": { members: [] },
      "/api/v1/procurement/lists": { lists: [] },
      "/api/v1/procurement/assignees": { assignees: [] },
      "/api/v1/suppliers": { suppliers: [] },
      "/api/v1/tenants/header-test/products": { products: [] },
      "/api/v1/supplier-purchases": { purchases: [] },
      "/api/v1/supplier-ledger/totals": { customers: [], suppliers: [] },
      "/api/v1/supplier-ledger/balances": { suppliers: [] },
    };
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const path = new URL(input instanceof Request ? input.url : input.toString()).pathname;
      if (!(path in answers)) throw new Error(`Unexpected request: ${path}`);
      return Promise.resolve(Response.json(answers[path]));
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter><Panel tenantId="header-test" /></MemoryRouter></QueryClientProvider>);
    await waitFor(() => {
      const header = screen.getByRole("heading", { level: 1, name: i18n.t(title) }).closest("header")!;
      expect(header.querySelector(".list-head-count")?.textContent).toBe(language === "ar" ? ar : en);
    });
    view.unmount();
    client.clear();
  });
}

test.each([
  { key: "customersPage.count", forms: ["لا عملاء", "عميل واحد", "عميلان", "<n>3</n> عملاء", "<n>17</n> عميلاً", "<n>100</n> عميل"] },
  { key: "delivery.count", forms: ["لا توصيلات", "توصيل واحد", "توصيلان", "<n>3</n> توصيلات", "<n>17</n> توصيلاً", "<n>100</n> توصيل"] },
  { key: "procurement.count", forms: ["لا قوائم", "قائمة واحدة", "قائمتان", "<n>3</n> قوائم", "<n>17</n> قائمة", "<n>100</n> قائمة"] },
  { key: "supplierSetup.count", forms: ["لا مورّدين", "مورّد واحد", "مورّدان", "<n>3</n> مورّدين", "<n>17</n> مورّدًا", "<n>100</n> مورّد"] },
])("Arabic $key covers every plural category and retains number markup", async ({ key, forms }) => {
  await i18n.changeLanguage("ar");
  expect([0, 1, 2, 3, 17, 100].map((count) => i18n.t(key, { count }))).toEqual(forms);
});
