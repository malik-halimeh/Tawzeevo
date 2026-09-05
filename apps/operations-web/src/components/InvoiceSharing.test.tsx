import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { InvoiceSharing } from "./InvoiceSharing";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("owner creates, shares, rotates and revokes a private invoice link without storing the secret", async () => {
  await i18n.changeLanguage("en");
  const requests: string[] = [];
  let revoked = false;
  let created = false;
  let generation = 1;
  const record = () => ({id: `link-${generation}`, created_at: "2026-09-05T10:00:00Z", expires_at: "2026-12-04T10:00:00Z", revoked_at: revoked ? "2026-09-05T10:01:00Z" : null});
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    requests.push(path);
    if (init?.method === "DELETE") {revoked = true; return Promise.resolve(new Response(null, {status:204}));}
    if (init?.method === "POST") {
      if (path.includes("/rotate")) generation++;
      created = true;
      return Promise.resolve(Response.json({...record(), public_path:`/api/v1/public/invoice#secret-${generation}`, customer_phone:"+96170123456", summary:"Invoice 2026-000001 · 10.0000 USD"}));
    }
    return Promise.resolve(Response.json(created ? [record()] : []));
  }));
  const storedBefore = {...localStorage};
  render(<InvoiceSharing tenantId="tenant" invoiceId="invoice" />);
  fireEvent.click(screen.getByRole("button", {name:"Manage invoice links"}));
  fireEvent.click(await screen.findByRole("button", {name:"Create private link"}));
  const whatsapp = await screen.findByRole("link", {name:"Share on WhatsApp"});
  const shared = new URL(whatsapp.getAttribute("href")!);
  expect(shared.hostname).toBe("wa.me");
  expect(shared.pathname).toBe("/96170123456");
  expect(shared.searchParams.get("text")).toContain("/api/v1/public/invoice#secret-1");
  expect(screen.getByRole("link", {name:"Open customer view"})).toHaveAttribute("rel", "noopener noreferrer");
  fireEvent.click(screen.getByRole("button", {name:"Replace link"}));
  await waitFor(() => expect(screen.getByLabelText("Private invoice URL")).toHaveValue("http://localhost:8000/api/v1/public/invoice#secret-2"));
  fireEvent.click(screen.getByRole("button", {name:"Revoke link"}));
  await waitFor(() => expect(screen.queryByRole("link", {name:"Share on WhatsApp"})).not.toBeInTheDocument());
  expect(requests.some(path => path.includes("link-1/rotate"))).toBe(true);
  expect({...localStorage}).toEqual(storedBefore);
});

test("invoice sharing supports Arabic labels and reports request failures", async () => {
  await i18n.changeLanguage("ar");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({detail:{code:"FAILED",message:"Try again"}}, {status:503}))));
  render(<InvoiceSharing tenantId="tenant" invoiceId="invoice" />);
  fireEvent.click(screen.getByRole("button", {name:"إدارة روابط الفاتورة"}));
  expect(await screen.findByText("Try again")).toBeVisible();
  expect(screen.getByRole("region", {name:"مشاركة الفاتورة"})).toBeVisible();
  await i18n.changeLanguage("en");
});
