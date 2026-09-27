import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { OwnerSetupChecklist } from "./OwnerSetupChecklist";

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function renderChecklist(activeCategories: number, published: number) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = new URL(input instanceof Request ? input.url : input.toString(), "http://localhost").pathname;
    if (path.endsWith("/categories")) return Promise.resolve(Response.json({ categories: Array.from({ length: activeCategories }, (_, index) => ({ id: `c${index}`, is_active: true, name_en: "Drinks", name_ar: "مشروبات", slug: "drinks", display_order: 1 })) }));
    if (path.endsWith("/storefront")) return Promise.resolve(Response.json({ slug: "cedar", previous_slugs: [], published_products: published, accepting_orders: published > 0, customer_access_policy: "LINK" }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><OwnerSetupChecklist tenantId="t1" /></MemoryRouter></QueryClientProvider>);
}

test("a new business sees the steps to get its shop ready, each one link away, with finished steps marked", async () => {
  renderChecklist(1, 0);
  const steps = await screen.findByRole("list");
  expect(screen.getByRole("heading", { name: "Get your shop ready" })).toBeInTheDocument();
  expect(within(steps).getAllByRole("link").map((link) => [link.textContent, link.getAttribute("href")])).toEqual([
    ["Add a category", "/workspace?tenant=t1&section=categories"],
    ["Add and publish a product", "/workspace?tenant=t1&section=products"],
    ["Copy your shop link", "/workspace?tenant=t1&section=storefront"],
    ["Set up branding (optional)", "/workspace?tenant=t1&section=branding"],
  ]);
  expect(within(steps).getAllByRole("listitem")[0]).toHaveTextContent("done"); // the category exists already
});

test("the checklist leaves once the shop has a category and a published product", async () => {
  const view = renderChecklist(2, 3);
  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(view.container).toBeEmptyDOMElement();
});
