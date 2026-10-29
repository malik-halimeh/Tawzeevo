import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
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
}
