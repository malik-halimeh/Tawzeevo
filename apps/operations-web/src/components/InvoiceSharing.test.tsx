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
  expect(await screen.findByText("Try again")).toBeVisible(); // the links load at once, so a failure shows at once
  expect(screen.getByRole("region", {name:"مشاركة الفاتورة"})).toBeVisible();
  await i18n.changeLanguage("en");
});

test("the issued share link can be copied, and a clipboard failure says how to copy it by hand", async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("fetch", vi.fn((_input: RequestInfo | URL, init?: RequestInit) => init?.method === "POST"
    ? Promise.resolve(Response.json({ id: "link-1", created_at: "2026-09-24T10:00:00Z", expires_at: "2026-12-23T10:00:00Z", revoked_at: null, public_path: "/api/v1/public/invoice#secret-9", customer_phone: null, summary: "Invoice 2026-000009" }))
    : Promise.resolve(Response.json([]))));
  const writeText = vi.fn(() => Promise.resolve());
  vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
  render(<InvoiceSharing tenantId="tenant" invoiceId="invoice" />);
  fireEvent.click(await screen.findByRole("button", { name: "Create private link" }));
  fireEvent.click(await screen.findByRole("button", { name: "Copy share link" }));
  await waitFor(() => expect(writeText).toHaveBeenCalledWith("http://localhost:8000/api/v1/public/invoice#secret-9"));
  expect(await screen.findByRole("button", { name: "Share link copied" })).toBeInTheDocument();

  writeText.mockImplementationOnce(() => Promise.reject(new Error("denied")));
  fireEvent.click(screen.getByRole("button", { name: "Share link copied" }));
  expect(await screen.findByText("Copy did not work; select the link and copy it.")).toBeInTheDocument();
});

test("one click sends the invoice on WhatsApp, replacing the current link when there is one", async () => {
  await i18n.changeLanguage("en");
  let active = false;
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    if (init?.method === "POST") {
      posts.push(path);
      active = true;
      return Promise.resolve(Response.json({ id: "link-1", created_at: "2026-09-24T10:00:00Z", expires_at: "2099-12-23T10:00:00Z", revoked_at: null, public_path: "/api/v1/public/invoice#secret-7", customer_phone: "+96170123456", summary: "Invoice 2026-000007" }));
    }
    return Promise.resolve(Response.json(active ? [{ id: "link-1", created_at: "2026-09-24T10:00:00Z", expires_at: "2099-12-23T10:00:00Z", revoked_at: null }] : []));
  }));
  const opened = { opener: {} as unknown, location: { href: "" }, close: vi.fn() };
  const open = vi.fn(() => opened);
  vi.stubGlobal("open", open);
  render(<InvoiceSharing tenantId="tenant" invoiceId="invoice" />);
  fireEvent.click(await screen.findByRole("button", { name: "Send on WhatsApp" }));
  await waitFor(() => expect(opened.location.href).toContain("https://wa.me/96170123456?text="));
  expect(opened.location.href).toContain(encodeURIComponent("/api/v1/public/invoice#secret-7"));
  expect(opened.opener).toBeNull(); // the chat window cannot reach back into the workspace
  expect(posts).toHaveLength(1);
  expect(posts[0]).not.toContain("/rotate");

  // With a live link, the same button replaces it (the old link stops working) and says so first.
  fireEvent.click(await screen.findByRole("button", { name: "Replace link and send on WhatsApp" }));
  expect(screen.getByText("Sending replaces the current link: the one sent before stops working.")).toBeInTheDocument();
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toContain("link-1/rotate");
});
