import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { App } from "./App";
import { clearSession } from "./api/client";
import type { Tenant, TenantApplication, User } from "./api/types";
import { AuthProvider } from "./auth/AuthContext";
import i18n from "./i18n";

const admin: User = {
  id: "11111111-1111-1111-1111-111111111111",
  first_name: "Maya",
  last_name: "Haddad",
  email: "admin@example.com",
  phone: "+96170123456",
  city: "Beirut",
  age: 34,
  type: "admin",
  created_at: "2026-08-20T08:00:00Z",
  updated_at: "2026-08-20T08:00:00Z",
};

const clientUser: User = { ...admin, id: "22222222-2222-2222-2222-222222222222", first_name: "Nour", email: "nour@example.com", type: "client" };

const application: TenantApplication = {
  id: "33333333-3333-3333-3333-333333333333",
  applicant_user_id: clientUser.id,
  business_name: "Cedar Distribution",
  status: "PENDING",
  reviewed_by_user_id: null,
  reviewed_at: null,
  review_notes: null,
  tenant_id: null,
  created_at: "2026-08-20T08:00:00Z",
  updated_at: "2026-08-20T08:00:00Z",
};

const tenant: Tenant = {
  id: "44444444-4444-4444-4444-444444444444",
  name: "North Route",
  status: "ACTIVE",
  access_until: "2026-09-20",
  grace_until: "2026-09-27",
  access_status: "current",
  suspension_reason: null,
  activated_at: "2026-08-20T08:00:00Z",
  suspended_at: null,
  reactivated_at: null,
  created_at: "2026-08-20T08:00:00Z",
  updated_at: "2026-08-20T08:00:00Z",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function unauthenticated(): Response {
  return json({ detail: { code: "INVALID_AUTHENTICATION", message: "Authentication is invalid" } }, 401);
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function requestBody(body: BodyInit | null | undefined): string {
  if (typeof body !== "string") throw new Error("Expected a JSON string body");
  return body;
}

function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider><App /></AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function authenticatedFetch(handler: (url: string, init?: RequestInit) => Promise<Response> | Response) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "access-token", token_type: "bearer", expires_in: 900 }));
    if (url.endsWith("/users/me") && (!init?.method || init.method === "GET")) return Promise.resolve(json(admin));
    return Promise.resolve(handler(url, init));
  });
}

beforeEach(async () => {
  clearSession();
  await i18n.changeLanguage("en");
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
  vi.stubGlobal("confirm", vi.fn(() => true));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("public and authentication flows", () => {
  test("renders live public statistics and switches the document to RTL", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      if (url.endsWith("/stats/count")) return Promise.resolve(json({ count: 8 }));
      if (url.endsWith("/stats/average-age")) return Promise.resolve(json({ average_age: 31.5 }));
      if (url.endsWith("/stats/top-cities")) return Promise.resolve(json([{ city: "Beirut", count: 4 }]));
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/stats");

    expect(await screen.findByText("8")).toBeInTheDocument();
    expect(screen.getByText("31.5")).toBeInTheDocument();
    expect(screen.getByText("Beirut")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /العربية/ }));
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByRole("heading", { name: /مجتمع توزيـفو/ })).toBeInTheDocument();
  });

  test("registers only the public client fields and returns to sign in", async () => {
    let registrationBody: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      if (url.endsWith("/register")) {
        registrationBody = JSON.parse(requestBody(init?.body)) as Record<string, unknown>;
        return Promise.resolve(json(clientUser, 201));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/register");

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Nour" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Haddad" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "nour@example.com" } });
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+96170123456" } });
    fireEvent.change(screen.getByLabelText("City"), { target: { value: "Beirut" } });
    fireEvent.change(screen.getByLabelText("Age"), { target: { value: "34" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a secure password" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "a secure password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create client account" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Account created");
    expect(registrationBody).toMatchObject({ email: "nour@example.com", first_name: "Nour" });
    expect(registrationBody).not.toHaveProperty("type");
    expect(registrationBody).not.toHaveProperty("password_confirmation");
  });

  test("signs in, keeps the access token out of storage, and opens the admin desk", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      if (url.endsWith("/login")) return Promise.resolve(json({ access_token: "admin-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) {
        expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer admin-access");
        return Promise.resolve(json(admin));
      }
      if (url.endsWith("/stats/count")) return Promise.resolve(json({ count: 5 }));
      if (url.includes("tenant-applications")) return Promise.resolve(json({ page: 1, limit: 1, total: 0, total_pages: 0, applications: [] }));
      if (url.includes("/platform/tenants")) return Promise.resolve(json({ page: 1, limit: 100, total: 0, total_pages: 0, tenants: [] }));
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/login");
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "admin@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a secure password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Operational overview" })).toBeInTheDocument();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test("redirects a protected route when refresh authentication fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(unauthenticated())));
    renderApp("/profile");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});

describe("platform administration flows", () => {
  test("creates a user through the real users contract", async () => {
    let users = [admin];
    let createdBody: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", authenticatedFetch((url, init) => {
      if (url.includes("/users?") && (!init?.method || init.method === "GET")) return json({ page: 1, limit: 10, total: users.length, total_pages: 1, users });
      if (url.endsWith("/users") && init?.method === "POST") {
        createdBody = JSON.parse(requestBody(init.body)) as Record<string, unknown>;
        users = [...users, clientUser];
        return json(clientUser, 201);
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/admin/users");
    expect(await screen.findByText("admin@example.com")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add user" }));
    const form = screen.getByRole("heading", { name: "Create user" }).closest("section");
    if (!form) throw new Error("User form not found");
    const fields = within(form);
    fireEvent.change(fields.getByLabelText("First name"), { target: { value: "Nour" } });
    fireEvent.change(fields.getByLabelText("Last name"), { target: { value: "Haddad" } });
    fireEvent.change(fields.getByLabelText("Email"), { target: { value: "nour@example.com" } });
    fireEvent.change(fields.getByLabelText("Phone"), { target: { value: "+96170123456" } });
    fireEvent.change(fields.getByLabelText("City"), { target: { value: "Beirut" } });
    fireEvent.change(fields.getByLabelText("Age"), { target: { value: "34" } });
    fireEvent.change(fields.getByLabelText("Password"), { target: { value: "a secure password" } });
    fireEvent.click(fields.getByRole("button", { name: "Create user" }));
    await waitFor(() => expect(createdBody).toMatchObject({ type: "client", email: "nour@example.com" }));
    expect(await screen.findByText("nour@example.com")).toBeInTheDocument();
  });

  test("approves a pending tenant application", async () => {
    let reviewed = false;
    vi.stubGlobal("fetch", authenticatedFetch((url, init) => {
      if (url.includes("/platform/tenant-applications") && (!init?.method || init.method === "GET")) return json({ page: 1, limit: 10, total: reviewed ? 0 : 1, total_pages: reviewed ? 0 : 1, applications: reviewed ? [] : [application] });
      if (url.endsWith(`/tenant-applications/${application.id}/approve`)) {
        reviewed = true;
        return json({ ...application, status: "APPROVED", tenant_id: tenant.id });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/admin/applications");
    expect(await screen.findByText("Cedar Distribution")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    fireEvent.click(screen.getByRole("button", { name: "Approve application" }));
    expect(await screen.findByRole("status")).toHaveTextContent("approved and activated");
  });

  test("suspends and reactivates the same tenant", async () => {
    let current = tenant;
    vi.stubGlobal("fetch", authenticatedFetch((url, init) => {
      if (url.includes("/platform/tenants?") && (!init?.method || init.method === "GET")) return json({ page: 1, limit: 10, total: 1, total_pages: 1, tenants: [current] });
      if (url.endsWith(`/tenants/${tenant.id}/suspend`)) {
        current = { ...current, status: "SUSPENDED", suspension_reason: "SUBSCRIPTION_OVERDUE" };
        return json(current);
      }
      if (url.endsWith(`/tenants/${tenant.id}/reactivate`)) {
        current = { ...current, status: "ACTIVE", suspension_reason: null };
        return json(current);
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/admin/tenants");
    expect(await screen.findByText("North Route")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Manage access and status" }));
    fireEvent.change(screen.getByLabelText("Access until"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save access period" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose an access end date");
    fireEvent.click(screen.getByRole("button", { name: "Suspend tenant" }));
    expect(await screen.findByRole("status")).toHaveTextContent("data remains stored");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reactivate tenant" }));
    expect(await screen.findByRole("status")).toHaveTextContent("reactivated with its retained data");
    expect(current.id).toBe(tenant.id);
  });
});
