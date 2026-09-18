import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { CustomerLinkControls } from "./CustomerLinkControls";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("owner issues a link shown once, rotates it, and revokes it", async () => {
  await i18n.changeLanguage("en");
  let active: Record<string, unknown> | null = null;
  const issued: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = input instanceof Request ? input.url : input.toString();
    if (path.includes("/access-link") && init?.method === "POST") {
      const secret = `${"a".repeat(32)}.${String(issued.length).padStart(43, "z")}`;
      issued.push(secret);
      active = { id: `link-${issued.length}`, customer_id: "c1", created_at: "2026-09-18T20:00:00Z", last_used_at: null, revoked_at: null, rotated_from_id: issued.length > 1 ? `link-${issued.length - 1}` : null };
      return Promise.resolve(Response.json({ ...active, storefront_path: `/cedar-van/access#${secret}` }, { status: 201 }));
    }
    if (path.includes("/access-link") && init?.method === "DELETE") {
      const revoked = { ...active, revoked_at: "2026-09-18T21:00:00Z" }; active = null;
      return Promise.resolve(Response.json(revoked));
    }
    if (path.includes("/access-link")) {
      return Promise.resolve(Response.json({ active, effective_policy: "LINK", policy_override: null, tenant_policy: "LINK", available_policies: ["LINK"] }));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: path } }, { status: 404 }));
  }));

  render(<CustomerLinkControls customerId="c1" tenantId="t1" />);
  expect(await screen.findByText(/No active link/)).toBeInTheDocument();
  expect(screen.getByText(/Access policy: Link \(no login\)/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Create personalized link" }));
  const url = await screen.findByLabelText<HTMLInputElement>("Personalized link");
  expect(url.value).toContain(`/cedar-van/access#${issued[0]}`);
  expect(screen.getByText(/shown only once/)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: /Replace link/ })).toBeInTheDocument());

  fireEvent.click(screen.getByRole("button", { name: /Replace link/ }));
  await waitFor(() => expect(screen.getByLabelText<HTMLInputElement>("Personalized link").value).toContain(issued[1]));
  expect(issued).toHaveLength(2);

  fireEvent.click(screen.getByRole("button", { name: "Revoke link" }));
  expect(await screen.findByText(/No active link/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Personalized link")).not.toBeInTheDocument();
});
