import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { TenantProduct } from "../api/types";
import i18n from "../i18n";
import { type Campaign, CampaignPanel } from "./CampaignPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const tenant = "11111111-1111-4111-8111-111111111111";
const product = { id: "product-1", name: "Cedar Water", is_published: true } as unknown as TenantProduct;
const hidden = { id: "product-2", name: "Hidden Labneh", is_published: false } as unknown as TenantProduct;

test("owner features a product, sees it live with priority, and can stop it (record kept)", async () => {
  await i18n.changeLanguage("en");
  const campaigns: Campaign[] = [];
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    if (path.includes("/storefront/campaigns") && init?.method === "POST" && path.includes("/cancel")) {
      const id = path.split("/campaigns/")[1]!.split("/")[0];
      const row = campaigns.find((c) => c.id === id)!;
      row.cancelled_at = "2026-09-18T10:00:00Z"; row.active = false;
      return Promise.resolve(Response.json(row));
    }
    if (path.includes("/storefront/campaigns") && init?.method === "POST") {
      const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<string, unknown>;
      bodies.push(body);
      const row: Campaign = { id: `c-${campaigns.length + 1}`, tenant_product_id: String(body.product_id), starts_at: "2026-09-18T09:00:00Z", ends_at: "2099-09-25T09:00:00Z", priority: Number(body.priority), created_at: "2026-09-18T09:00:00Z", cancelled_at: null, active: true };
      campaigns.unshift(row);
      return Promise.resolve(Response.json(row, { status: 201 }));
    }
    if (path.includes("/storefront/campaigns")) return Promise.resolve(Response.json({ campaigns }));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<CampaignPanel products={[product, hidden]} tenantId={tenant} />);
  expect(await screen.findByText("No campaigns yet.")).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Hidden Labneh · not published" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Product" }), { target: { value: "product-1" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "Priority (higher first)" }), { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Feature this product" }));
  expect(await screen.findByText("Campaign saved.")).toBeInTheDocument();
  expect(bodies[0]).toEqual({ product_id: "product-1", priority: 5 });
  await waitFor(() => expect(screen.getAllByText("Cedar Water")).toHaveLength(2)); // option + campaign row
  expect(screen.getByText("Live")).toBeInTheDocument();
  expect(screen.getByText(/priority 5/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Stop featuring" }));
  expect(await screen.findByText("Campaign cancelled; the record is kept.")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("Cancelled")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "Stop featuring" })).not.toBeInTheDocument();
});
