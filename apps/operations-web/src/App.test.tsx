import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { MemoryRouter, type NavigateFunction, useNavigate } from "react-router-dom";

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

/**
 * The desktop rail's navigation. jsdom renders every layout at once; the phone bar is the separate
 * "Primary navigation", so rail queries are scoped to this landmark.
 */
const railNav = () => screen.getByRole("navigation", { name: "Workspace navigation" });
const railLink = (name: string) => within(railNav()).getByRole("link", { name });
const railLinks = () => within(railNav()).getAllByRole("link").map((link) => link.textContent);

/** Stands in for the browser's back/forward buttons inside the memory router. */
let browserNavigate: NavigateFunction | undefined;
function NavigationProbe() {
  browserNavigate = useNavigate();
  return null;
}

function renderApp(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <NavigationProbe />
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
  test("shows explicit loading states while public data and a protected session are pending", async () => {
    const pendingStatistics: Array<{ url: string; resolve: (response: Response) => void }> = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      return new Promise<Response>((resolve) => pendingStatistics.push({ url, resolve }));
    }));
    const publicView = renderApp("/stats");
    expect(screen.getByRole("status")).toHaveTextContent("Loading current data");
    await waitFor(() => expect(pendingStatistics).toHaveLength(3));
    for (const pending of pendingStatistics) {
      if (pending.url.endsWith("/stats/count")) pending.resolve(json({ count: 0 }));
      if (pending.url.endsWith("/stats/average-age")) pending.resolve(json({ average_age: null }));
      if (pending.url.endsWith("/stats/top-cities")) pending.resolve(json([]));
    }
    expect(await screen.findByLabelText("Platform statistics summary")).toBeInTheDocument();
    publicView.unmount();

    let finishRefresh: ((response: Response) => void) | undefined;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { finishRefresh = resolve; })));
    renderApp("/profile");
    expect(screen.getByRole("status")).toHaveTextContent("Restoring your secure session");
    await waitFor(() => expect(finishRefresh).toBeDefined());
    finishRefresh?.(unauthenticated());
    expect(await screen.findByRole("heading", { name: "Welcome back." })).toBeInTheDocument();
  });

  test("shows a translated API error state without rendering stale statistics", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      if (url.includes("/stats/")) {
        return Promise.resolve(json({ detail: { code: "DATABASE_UNAVAILABLE", message: "Database is unavailable" } }, 503));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/stats");

    expect(await screen.findByRole("alert")).toHaveTextContent("The request could not be completed");
    expect(screen.getByRole("alert")).toHaveTextContent("Database is unavailable");
    expect(screen.queryByLabelText("Platform statistics summary")).not.toBeInTheDocument();
  });

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
    await waitFor(() => {
      expect(document.documentElement.dir).toBe("rtl");
      expect(document.documentElement.lang).toBe("ar");
    });
    expect(screen.getByRole("heading", { name: /مجتمع توزيـفو/ })).toBeInTheDocument();
  });

  test("keeps phone entry left-to-right inside the Arabic registration layout", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(unauthenticated())));
    renderApp("/register");
    fireEvent.click(screen.getByRole("button", { name: /العربية/ }));

    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByRole("heading", { name: "إنشاء حساب" })).toBeInTheDocument();
    expect(screen.getByLabelText("الهاتف")).toHaveAttribute("dir", "ltr");
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
    expect(await screen.findByRole("heading", { name: "Welcome back." })).toBeInTheDocument();
  });

  test("the root route is the public landing page and keeps the statistics one link away", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(unauthenticated())));
    renderApp("/");
    expect(await screen.findByRole("heading", { level: 1, name: /Your business\./ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in to your workspace" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Public statistics" })).toHaveAttribute("href", "/stats");
    expect(screen.queryByRole("link", { name: /sample workday|workspace preview/i })).not.toBeInTheDocument(); // reviewer tools stay out of production builds
    expect(screen.queryByText(/tracking|in stock|out of stock/i)).not.toBeInTheDocument();
    // Decorative icons are hidden from assistive technology; every button and link has a name.
    for (const svg of document.querySelectorAll("svg")) expect(svg).toHaveAttribute("aria-hidden", "true");
    for (const control of screen.getAllByRole("link")) expect(control).toHaveAccessibleName();

    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByRole("heading", { level: 1, name: /أعمالك\./ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ادخل إلى مساحة عملك" })).toHaveAttribute("href", "/login");
  });

  test("sign-in keeps its behaviour inside the new frame: reveal toggle, validation, requested path", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      calls.push(url);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      if (url.endsWith("/login")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) {
        expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer client-access");
        return Promise.resolve(json(clientUser));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/profile"); // protected: the guard sends the visitor to sign in and remembers the requested path
    expect(await screen.findByRole("heading", { name: "Welcome back." })).toBeInTheDocument();
    expect(screen.getByText(/Open the storefront link shared by your supplier/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /customer account|customer sign in/i })).not.toBeInTheDocument();

    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    const reveal = screen.getByRole("button", { name: "Show password" });
    expect(reveal).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(reveal);
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findAllByRole("alert")).toHaveLength(2); // both fields validated before any request
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
    expect(calls.filter((url) => url.endsWith("/login"))).toHaveLength(0);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "nour@example.com" } });
    fireEvent.change(password, { target: { value: "a secure password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument(); // the requested path, not the default workspace
    expect(localStorage.length).toBe(0);
  });
});

describe("tenant customer and category workspace", () => {
  test("keeps duplicate phone matches separate and updates the selected customer", async () => {
    const context = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status: "ACTIVE", role: "owner" };
    const customers = [
      { id: "66666666-6666-6666-6666-666666666666", tenant_id: tenant.id, name: "Maya Market", phone: "+96170123456", address: "Hamra, Beirut", latitude: null, longitude: null, grade: "A+", created_at: tenant.created_at, updated_at: tenant.updated_at },
      { id: "77777777-7777-7777-7777-777777777777", tenant_id: tenant.id, name: "Maya Market — Branch 2", phone: "+96170123456", address: "Verdun, Beirut", latitude: null, longitude: null, grade: "B+", created_at: tenant.created_at, updated_at: tenant.updated_at },
    ];
    let updateBody: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [context] }));
      if (url.includes("/delivery-tasks/my-work")) return Promise.resolve(json({ tasks: [], membership_id: context.membership_id, role: "owner" })); // Work is the default section
      if (url.includes("/customers/search?")) return Promise.resolve(json({ customers }));
      if (url.endsWith(`/customers/${customers[1]!.id}`) && init?.method === "PUT") {
        updateBody = JSON.parse(requestBody(init.body)) as Record<string, unknown>;
        return Promise.resolve(json({ ...customers[1], ...updateBody }));
      }
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [] }));
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/workspace");

    expect(await screen.findByRole("heading", { name: "North Route" })).toBeInTheDocument();
    fireEvent.click(railLink("Customers"));
    const lookup = screen.getByRole("heading", { name: "Find every matching customer" }).closest("article");
    if (!lookup) throw new Error("Customer lookup not found");
    fireEvent.change(within(lookup).getByLabelText("Phone"), { target: { value: "70 123 456" } });
    fireEvent.click(within(lookup).getByRole("button", { name: "Search" }));

    expect(await screen.findByText("Hamra, Beirut")).toBeInTheDocument();
    expect(screen.getByText("Verdun, Beirut")).toBeInTheDocument();
    expect(screen.getByText(customers[0]!.id)).toHaveAttribute("dir", "ltr");
    const secondMatch = screen.getByText("Maya Market — Branch 2").closest("article");
    if (!secondMatch) throw new Error("Second customer match not found");
    fireEvent.click(within(secondMatch).getByRole("button", { name: "Edit" }));
    const customerForm = screen.getByRole("heading", { name: "Edit customer" }).closest("article");
    if (!customerForm) throw new Error("Customer form not found");
    fireEvent.change(within(customerForm).getByLabelText("Address"), { target: { value: "Achrafieh, Beirut" } });
    fireEvent.change(within(customerForm).getByLabelText("Grade"), { target: { value: "A" } });
    fireEvent.click(within(customerForm).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(updateBody).toMatchObject({ address: "Achrafieh, Beirut", grade: "A" }));
  });

  test("shows bilingual ordered categories, archives safely, and remains usable in RTL", async () => {
    const context = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status: "ACTIVE", role: "owner" };
    let category = { id: "88888888-8888-8888-8888-888888888888", tenant_id: tenant.id, master_category_id: null, name_en: "Cold drinks", name_ar: "مشروبات باردة", slug: "cold-drinks", display_order: 10, is_active: true, archived_at: null as string | null, created_at: tenant.created_at, updated_at: tenant.updated_at };
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [context] }));
      if (url.includes("/delivery-tasks/my-work")) return Promise.resolve(json({ tasks: [], membership_id: context.membership_id, role: "owner" })); // Work is the default section
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [category] }));
      if (url.endsWith(`/categories/${category.id}/archive`) && init?.method === "POST") {
        category = { ...category, is_active: false, archived_at: "2026-08-25T09:00:00Z" };
        return Promise.resolve(json(category));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/workspace");
    await screen.findByRole("heading", { name: "North Route" });
    fireEvent.click(railLink("Categories"));

    expect(await screen.findByText("Cold drinks")).toBeInTheDocument();
    expect(screen.getByText("مشروبات باردة")).toHaveAttribute("dir", "rtl");
    expect(screen.getByText("10")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(await screen.findByRole("status")).toHaveTextContent("without deleting its history");
    expect(screen.getByRole("button", { name: "Archived" })).toBeDisabled();

    fireEvent.click(screen.getAllByRole("button", { name: "العربية" })[0]!);
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByLabelText("الاسم بالعربية")).toHaveAttribute("dir", "rtl");
    expect(screen.getByLabelText("رابط واجهة المتجر")).toHaveAttribute("dir", "ltr");
  });

  test("scans a known master barcode and adopts it with tenant price and visibility", async () => {
    const context = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status: "ACTIVE", role: "owner" };
    const category = { id: "88888888-8888-8888-8888-888888888888", tenant_id: tenant.id, master_category_id: null, name_en: "Drinks", name_ar: "مشروبات", slug: "drinks", display_order: 1, is_active: true, archived_at: null, created_at: tenant.created_at, updated_at: tenant.updated_at };
    const masterId = "99999999-9999-9999-9999-999999999999";
    let products: Record<string, unknown>[] = [];
    let createBody: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [context] }));
      if (url.includes("/delivery-tasks/my-work")) return Promise.resolve(json({ tasks: [], membership_id: context.membership_id, role: "owner" })); // Work is the default section
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [category] }));
      if (url.endsWith("/grade-discounts")) return Promise.resolve(json({ discounts: [] }));
      if (url.endsWith("/products") && (!init?.method || init.method === "GET")) return Promise.resolve(json({ products }));
      if (url.endsWith("/catalog/barcodes/012345")) return Promise.resolve(json({ barcode: "012345", ownership: "MASTER", package_level: "PIECE", master_product: { id: masterId, master_category_id: null, name: "Cedar Water 500ml", barcodes: [{ id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", barcode: "012345", package_level: "PIECE", ownership: "MASTER" }], images: [], created_at: tenant.created_at, updated_at: tenant.updated_at }, tenant_product: null }));
      if (url.endsWith("/products") && init?.method === "POST") {
        createBody = JSON.parse(requestBody(init.body)) as Record<string, unknown>;
        const product = { id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", tenant_id: tenant.id, ...createBody, master_product_id: masterId, barcode: "012345", barcodes: [{ id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", barcode: "012345", package_level: "PIECE", ownership: "MASTER" }], images: [], grade_prices: [], piece_price: "1.2500", box_price: null, created_at: tenant.created_at, updated_at: tenant.updated_at };
        products = [product];
        return Promise.resolve(json(product, 201));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/workspace");
    await screen.findByRole("heading", { name: "North Route" });
    fireEvent.click(railLink("Products"));
    const scanDesk = screen.getByRole("heading", { name: "Scan once. Resolve the right catalog identity." }).closest("article");
    if (!scanDesk) throw new Error("Scan desk not found");
    fireEvent.change(within(scanDesk).getByLabelText("Barcode"), { target: { value: "012345" } });
    fireEvent.click(within(scanDesk).getByRole("button", { name: "Scan barcode" }));
    expect(await screen.findByText("Cedar Water 500ml")).toBeInTheDocument();

    const productForm = screen.getByRole("heading", { name: "Product details" }).closest("article");
    if (!productForm) throw new Error("Product form not found");
    fireEvent.change(within(productForm).getByLabelText("Category"), { target: { value: category.id } });
    fireEvent.change(within(productForm).getByLabelText("Tenant price"), { target: { value: "1.25" } });
    fireEvent.click(within(productForm).getByLabelText("Publish this product in customer-facing catalog views"));
    fireEvent.click(within(productForm).getByRole("button", { name: "Save tenant product" }));

    await waitFor(() => expect(createBody).toMatchObject({ master_product_id: masterId, barcode: "012345", category_id: category.id, unit_price: "1.25", is_published: true }));
    expect(await screen.findByText("1.25 USD / PIECE")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  test("turns an unknown scan into a manual product and adds a package barcode", async () => {
    const context = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status: "ACTIVE", role: "owner" };
    const category = { id: "88888888-8888-8888-8888-888888888888", tenant_id: tenant.id, master_category_id: null, name_en: "Snacks", name_ar: "وجبات", slug: "snacks", display_order: 1, is_active: true, archived_at: null, created_at: tenant.created_at, updated_at: tenant.updated_at };
    const productId = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
    let product = { id: productId, tenant_id: tenant.id, category_id: category.id, master_product_id: null, name: "Local Chips", barcode: "LOCAL-1", barcodes: [{ id: "cccccccc-cccc-cccc-cccc-cccccccccccc", barcode: "LOCAL-1", package_level: "PIECE", ownership: "TENANT" }], images: [], grade_prices: [], is_published: false, unit_price: "0.7500", currency: "USD", price_basis: "PIECE", pieces_per_box: null, piece_price: "0.7500", box_price: null, created_at: tenant.created_at, updated_at: tenant.updated_at };
    let products: typeof product[] = [];
    let addedBarcode: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [context] }));
      if (url.includes("/delivery-tasks/my-work")) return Promise.resolve(json({ tasks: [], membership_id: context.membership_id, role: "owner" })); // Work is the default section
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [category] }));
      if (url.endsWith("/grade-discounts")) return Promise.resolve(json({ discounts: [] }));
      if (url.endsWith("/products") && (!init?.method || init.method === "GET")) return Promise.resolve(json({ products }));
      if (url.endsWith("/catalog/barcodes/LOCAL-1")) return Promise.resolve(json({ detail: { code: "BARCODE_NOT_FOUND", message: "Barcode was not found" } }, 404));
      if (url.endsWith("/products") && init?.method === "POST") { products = [product]; return Promise.resolve(json(product, 201)); }
      if (url.endsWith(`/products/${productId}/barcodes`) && init?.method === "POST") {
        addedBarcode = JSON.parse(requestBody(init.body)) as Record<string, unknown>;
        product = { ...product, barcodes: [...product.barcodes, { id: "dddddddd-dddd-dddd-dddd-dddddddddddd", barcode: String(addedBarcode.barcode), package_level: "BOX", ownership: "TENANT" }] };
        products = [product];
        return Promise.resolve(json(product, 201));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/workspace");
    await screen.findByRole("heading", { name: "North Route" });
    fireEvent.click(railLink("Products"));
    const scanDesk = screen.getByRole("heading", { name: "Scan once. Resolve the right catalog identity." }).closest("article")!;
    fireEvent.change(within(scanDesk).getByLabelText("Barcode"), { target: { value: "LOCAL-1" } });
    fireEvent.click(within(scanDesk).getByRole("button", { name: "Scan barcode" }));
    expect(await screen.findByText(/Barcode not found in the master catalog/)).toBeInTheDocument();
    const productForm = screen.getByRole("heading", { name: "Product details" }).closest("article")!;
    expect(within(productForm).getByLabelText("Barcode")).toHaveValue("LOCAL-1");
    fireEvent.change(within(productForm).getByLabelText("Product name"), { target: { value: "Local Chips" } });
    fireEvent.change(within(productForm).getByLabelText("Category"), { target: { value: category.id } });
    fireEvent.change(within(productForm).getByLabelText("Tenant price"), { target: { value: "0.75" } });
    fireEvent.click(within(productForm).getByRole("button", { name: "Save tenant product" }));
    expect(await screen.findByText("Local Chips")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add package barcode" }));
    const barcodeForm = screen.getByRole("button", { name: "Save changes" }).closest("form")!;
    fireEvent.change(within(barcodeForm).getByLabelText("Barcode"), { target: { value: "LOCAL-BOX-1" } });
    fireEvent.change(within(barcodeForm).getByLabelText("Barcode package"), { target: { value: "BOX" } });
    fireEvent.click(within(barcodeForm).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(addedBarcode).toEqual({ barcode: "LOCAL-BOX-1", package_level: "BOX" }));
    expect(await screen.findByText(/LOCAL-BOX-1/)).toBeInTheDocument();
  });

  test("manages grade pricing and uploads an authenticated product image", async () => {
    const context = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status: "ACTIVE", role: "owner" };
    const category = { id: "88888888-8888-8888-8888-888888888888", tenant_id: tenant.id, master_category_id: null, name_en: "Drinks", name_ar: "مشروبات", slug: "drinks", display_order: 1, is_active: true, archived_at: null, created_at: tenant.created_at, updated_at: tenant.updated_at };
    const productId = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
    const imageId = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee";
    let discounts: Record<string, unknown>[] = [];
    let discountBody: Record<string, unknown> | undefined;
    let gradePriceBody: Record<string, unknown> | undefined;
    let uploadBody: FormData | undefined;
    let uploadSetContentType = false;
    let product = { id: productId, tenant_id: tenant.id, category_id: category.id, master_product_id: null, name: "Cedar Juice", barcode: "JUICE-1", barcodes: [{ id: "cccccccc-cccc-cccc-cccc-cccccccccccc", barcode: "JUICE-1", package_level: "PIECE", ownership: "TENANT" }], images: [] as Record<string, unknown>[], grade_prices: [] as Record<string, unknown>[], is_published: true, unit_price: "3.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6, piece_price: "3.0000", box_price: "18.0000", created_at: tenant.created_at, updated_at: tenant.updated_at };
    const createObjectURL = vi.fn(() => "blob:tawzeevo-product");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", class extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    });
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [context] }));
      if (url.includes("/delivery-tasks/my-work")) return Promise.resolve(json({ tasks: [], membership_id: context.membership_id, role: "owner" })); // Work is the default section
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [category] }));
      if (url.endsWith("/products") && (!init?.method || init.method === "GET")) return Promise.resolve(json({ products: [product] }));
      if (url.endsWith("/grade-discounts") && (!init?.method || init.method === "GET")) return Promise.resolve(json({ discounts }));
      if (url.endsWith("/grade-discounts/A") && init?.method === "PUT") {
        discountBody = JSON.parse(requestBody(init.body)) as Record<string, unknown>;
        const saved = { id: "dddddddd-dddd-dddd-dddd-dddddddddddd", tenant_id: tenant.id, grade: "A", discount_percent: "7.5000", created_at: tenant.created_at, updated_at: tenant.updated_at };
        discounts = [saved];
        return Promise.resolve(json(saved));
      }
      if (url.endsWith(`/products/${productId}/grade-prices/A%2B`) && init?.method === "PUT") {
        gradePriceBody = JSON.parse(requestBody(init.body)) as Record<string, unknown>;
        const saved = { id: "ffffffff-ffff-ffff-ffff-ffffffffffff", tenant_id: tenant.id, tenant_product_id: productId, grade: "A+", unit_price: "2.5000", created_at: tenant.created_at, updated_at: tenant.updated_at };
        product = { ...product, grade_prices: [saved] };
        return Promise.resolve(json(saved));
      }
      if (url.endsWith(`/products/${productId}/images`) && init?.method === "POST") {
        uploadBody = init.body as FormData;
        uploadSetContentType = new Headers(init.headers).has("Content-Type");
        const saved = { id: imageId, ownership: "TENANT", content_type: "image/webp", byte_size: 100, width: 16, height: 10, display_order: 0, alt_text: "Juice bottle", url: `/api/v1/tenants/${tenant.id}/product-images/TENANT/${imageId}/content` };
        product = { ...product, images: [saved] };
        return Promise.resolve(json(saved, 201));
      }
      if (url.endsWith(`/product-images/TENANT/${imageId}/content`)) {
        return Promise.resolve(new Response(new Blob(["webp"], { type: "image/webp" }), { headers: { "Content-Type": "image/webp" } }));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));

    renderApp("/workspace");
    await screen.findByRole("heading", { name: "North Route" });
    fireEvent.click(railLink("Products"));
    const discountInput = await screen.findByLabelText("Grade A discount (%)");
    fireEvent.change(discountInput, { target: { value: "7.5" } });
    await waitFor(() => expect(discountInput).toHaveValue(7.5));
    fireEvent.click(within(discountInput.closest("form")!).getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(discountBody).toEqual({ discount_percent: "7.5" }));

    const productCard = (await screen.findByRole("heading", { name: "Cedar Juice" })).closest("article")!;
    fireEvent.change(within(productCard).getByLabelText("Grade basis price"), { target: { value: "2.5" } });
    fireEvent.click(within(productCard).getByRole("button", { name: "Save grade price" }));
    await waitFor(() => expect(gradePriceBody).toEqual({ unit_price: "2.5" }));
    expect(await within(productCard).findByText(/2.5000 USD/)).toBeInTheDocument();

    const file = new File(["png"], "juice.png", { type: "image/png" });
    fireEvent.change(within(productCard).getByLabelText("Product image"), { target: { files: [file] } });
    fireEvent.change(within(productCard).getByLabelText("Image description"), { target: { value: "Juice bottle" } });
    const uploadButton = within(productCard).getByRole("button", { name: "Upload image" });
    await waitFor(() => expect(uploadButton).toBeEnabled());
    fireEvent.submit(uploadButton.closest("form")!);
    await waitFor(() => expect(uploadBody).toBeInstanceOf(FormData));
    expect(uploadBody?.get("file")).toBe(file);
    expect(uploadBody?.get("alt_text")).toBe("Juice bottle");
    expect(uploadSetContentType).toBe(false);
    const image = await within(productCard).findByRole("img", { name: "Juice bottle" });
    expect(image).toHaveAttribute("src", "blob:tawzeevo-product");
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

  test("password recovery: forgot page answers the same for any address; reset page sends the fragment token once", async () => {
    const calls: { url: string; body: Record<string, unknown> }[] = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(unauthenticated());
      if (url.endsWith("/api/v1/auth/password/forgot")) {
        calls.push({ url, body: JSON.parse(requestBody(init?.body)) as Record<string, unknown> });
        return Promise.resolve(json({ status: "accepted" }, 202));
      }
      if (url.endsWith("/api/v1/auth/password/reset")) {
        calls.push({ url, body: JSON.parse(requestBody(init?.body)) as Record<string, unknown> });
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      throw new Error(`Unexpected request: ${url}`);
    }));
    renderApp("/login");
    fireEvent.click(screen.getByRole("link", { name: "Forgot your password?" }));
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "nobody@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send me a reset link" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If that address belongs to an account");
    expect(calls[0]?.body).toEqual({ email: "nobody@example.com" });
    expect(calls[0]?.url).not.toContain("nobody"); // the address travels in the body, never the URL
    cleanup();

    window.location.hash = "#one-time-token-from-the-mail";
    renderApp("/reset-password");
    fireEvent.change(await screen.findByLabelText("Password"), { target: { value: "brand new passphrase" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "brand new passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1]?.body).toEqual({ token: "one-time-token-from-the-mail", password: "brand new passphrase" });
    expect(await screen.findByRole("status")).toHaveTextContent("Your password was changed");
    expect(window.location.hash).toBe(""); // the token is dropped from the address bar after use
  });
});

describe("phone navigation follows the member's role", () => {
  const stop = { id: "t1", status: "ASSIGNED", official_invoice_number: "2026-000481", customer_name: "Corner Shop", customer_phone: "+96170123456", customer_address: "Hamra, Beirut", customer_latitude: null, customer_longitude: null, delivery_date: "2026-09-22", route_sequence: 1, currency: "USD", amount_to_collect: "30.0000", items: [{ product_name: "Water", quantity: "2.0000", price_basis: "PIECE", pieces_per_box: null }], notes: null, version: 1 };
  const memberFetch = (role: "owner" | "driver", tenant_status: "ACTIVE" | "SUSPENDED" = "ACTIVE") => {
    const context = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status, role };
    return vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [context] }));
      if (url.includes("/delivery-tasks/my-work")) return Promise.resolve(json({ tasks: [stop], membership_id: context.membership_id, role }));
      if (url.includes("/procurement/my-pickups")) return Promise.resolve(json({ lists: [] }));
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [] }));
      throw new Error(`Unexpected request: ${url}`);
    });
  };
  const primaryNav = () => screen.getByRole("navigation", { name: "Primary navigation" });
  const primaryLinks = () => within(primaryNav()).getAllByRole("link").map((link) => link.textContent);
  const moreSheet = () => screen.getByRole("group", { name: "More options" });
  // The compact business header is the page heading of an active workspace.
  const businessHeader = () => screen.getByRole("heading", { level: 1 }).closest("header")!;
  const businessRole = () => within(businessHeader()).getByText(/^(Owner|Driver)$/).textContent;

  // One person, two memberships: owner of North Route, driver for Harbour Line (synthetic).
  const harbour = { id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", name: "Harbour Line" };
  const mixedFetch = () => {
    const ownerContext = { membership_id: "55555555-5555-5555-5555-555555555555", tenant_id: tenant.id, tenant_name: tenant.name, tenant_status: "ACTIVE", role: "owner" };
    const driverContext = { membership_id: "66666666-6666-6666-6666-666666666666", tenant_id: harbour.id, tenant_name: harbour.name, tenant_status: "ACTIVE", role: "driver" };
    const harbourStop = { ...stop, id: "t2", customer_name: "Harbour Kiosk", customer_address: "Port, Saida", amount_to_collect: "12.0000" };
    let ownerStopDelivered = false;
    return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/refresh")) return Promise.resolve(json({ access_token: "client-access", token_type: "bearer", expires_in: 900 }));
      if (url.endsWith("/users/me")) return Promise.resolve(json(clientUser));
      if (url.endsWith("/api/v1/tenant-contexts")) return Promise.resolve(json({ tenants: [ownerContext, driverContext] }));
      if (url.includes("/delivery-tasks/my-work")) {
        return Promise.resolve(url.endsWith(`tenant_id=${harbour.id}`)
          ? json({ tasks: [harbourStop], membership_id: driverContext.membership_id, role: "driver" })
          : json({ tasks: ownerStopDelivered ? [] : [stop], membership_id: ownerContext.membership_id, role: "owner" }));
      }
      if (url.includes(`/delivery-tasks/${stop.id}/complete`) && init?.method === "POST") { ownerStopDelivered = true; return Promise.resolve(json({ ...stop, status: "COMPLETED", version: 2 })); }
      if (url.includes("/procurement/my-pickups")) return Promise.resolve(json({ lists: [] }));
      if (url.includes("/categories?")) return Promise.resolve(json({ categories: [] }));
      throw new Error(`Unexpected request: ${url}`);
    });
  };

  test("an owner gets Work, Customers, Invoices and More; Work opens on the stop list and More reaches every other section", async () => {
    vi.stubGlobal("fetch", memberFetch("owner"));
    renderApp("/workspace");
    expect(await screen.findByRole("heading", { name: "My route" })).toBeInTheDocument(); // the assigned-stop workflow comes first
    expect(await screen.findByRole("button", { name: /01.*Corner Shop/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Find every matching customer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /My deliveries|^Deliveries$/ })).not.toBeInTheDocument(); // management forms never sit in front of the route

    expect(within(primaryNav()).getAllByRole("link").map((link) => link.textContent)).toEqual(["Work", "Customers", "Invoices"]);
    expect(within(primaryNav()).getByRole("link", { name: "Work" })).toHaveAttribute("aria-current", "page");

    // With a stop open, tapping Work returns to the stop list (as the driver's My work anchor does).
    const route = screen.getByRole("region", { name: "My route" });
    fireEvent.click(screen.getByRole("button", { name: /01.*Corner Shop/ }));
    expect(route).toHaveClass("show-detail");
    fireEvent.click(within(primaryNav()).getByRole("link", { name: "Work" }));
    await waitFor(() => expect(route).not.toHaveClass("show-detail"));
    expect(within(primaryNav()).getByRole("link", { name: "Work" })).toHaveAttribute("href", "/workspace");

    fireEvent.click(within(primaryNav()).getByRole("link", { name: "Customers" }));
    expect(await screen.findByRole("heading", { name: "Find every matching customer" })).toBeInTheDocument();
    expect(within(primaryNav()).getByRole("link", { name: "Customers" })).toHaveAttribute("aria-current", "page");
    expect(railLink("Customers")).toHaveAttribute("aria-current", "page"); // the desktop rail shows the same section

    const more = within(primaryNav()).getByRole("button", { name: "More" });
    fireEvent.click(more);
    expect(more).toHaveAttribute("aria-expanded", "true");
    expect(within(moreSheet()).getAllByRole("link").map((link) => link.textContent)).toEqual(["Orders", "Deliveries", "Categories", "Products", "Suppliers & costs", "Procurement", "Analytics", "Branding", "Offline", "Backup", "Profile", "Public statistics"]);
    expect(within(moreSheet()).getByRole("link", { name: "Deliveries" })).toHaveAttribute("href", "/workspace?section=deliveries"); // management stays one step away
    expect(within(moreSheet()).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("group", { name: "More options" })).not.toBeInTheDocument();
    expect(more).toHaveFocus();

    fireEvent.click(more);
    fireEvent.click(within(moreSheet()).getByRole("link", { name: "Categories" }));
    await waitFor(() => expect(railLink("Categories")).toHaveAttribute("aria-current", "page"));
    expect(screen.queryByRole("group", { name: "More options" })).not.toBeInTheDocument(); // the sheet closes once the section opens
  });

  test("an owner's desktop rail carries every section once, grouped like the phone, and the business header leads the page", async () => {
    vi.stubGlobal("fetch", memberFetch("owner"));
    renderApp("/workspace");
    expect(await screen.findByRole("button", { name: /01.*Corner Shop/ })).toBeInTheDocument();
    expect(railLinks()).toEqual(["Work", "Customers", "Invoices", "Orders", "Deliveries", "Categories", "Products", "Suppliers & costs", "Procurement", "Analytics", "Branding", "Offline", "Backup"]);
    const railMore = within(railNav()).getByRole("group", { name: "More" });
    expect(within(railMore).getAllByRole("link").map((link) => link.textContent)).toEqual(["Orders", "Deliveries", "Categories", "Products", "Suppliers & costs", "Procurement", "Analytics", "Branding", "Offline", "Backup"]);
    expect(railLink("Work")).toHaveAttribute("aria-current", "page");
    expect(railLink("Analytics")).toHaveAttribute("href", "/workspace?section=analytics");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument(); // no section strip between the member and the work
    expect(within(screen.getByRole("group", { name: "Account" })).getAllByRole("link").map((link) => link.textContent)).toEqual(["Profile", "Public statistics"]);

    // The page heading is the selected business with its state and role; no generic greeting precedes the route.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("North Route");
    expect(within(businessHeader()).getByText("Active")).toBeInTheDocument();
    expect(businessRole()).toBe("Owner");
    expect(screen.queryByText(/Welcome, Nour/)).not.toBeInTheDocument();

    fireEvent.click(railLink("Customers"));
    expect(await screen.findByRole("heading", { name: "Find every matching customer" })).toBeInTheDocument();
    expect(railLink("Customers")).toHaveAttribute("aria-current", "page");
    expect(railLink("Work")).not.toHaveAttribute("aria-current");
  });

  test("a driver gets My work and Sync only and never an owner section", async () => {
    vi.stubGlobal("fetch", memberFetch("driver"));
    renderApp("/workspace");
    expect(await screen.findByRole("heading", { name: "My route" })).toBeInTheDocument();
    expect(within(primaryNav()).getAllByRole("link").map((link) => link.textContent)).toEqual(["My work", "Sync"]);
    expect(within(primaryNav()).getByRole("link", { name: "Sync" })).toHaveAttribute("href", "/workspace#my-work-sync");
    expect(railLinks()).toEqual(["My work", "Sync"]); // the desktop rail offers the same driver grouping
    expect(railLink("Sync")).toHaveAttribute("href", "/workspace#my-work-sync");
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(businessRole()).toBe("Driver");
    expect(screen.queryByText(/does not have owner permission/)).not.toBeInTheDocument(); // a valid driver membership is not a permission problem

    fireEvent.click(within(primaryNav()).getByRole("button", { name: "More" }));
    expect(within(moreSheet()).getAllByRole("link").map((link) => link.textContent)).toEqual(["Profile", "Public statistics"]);
    expect(moreSheet().textContent).not.toMatch(/customers|invoices|deliveries|analytics|branding|backup|cost|margin|profit/i);
    fireEvent.click(within(moreSheet()).getByRole("button", { name: "Close menu" }));

    fireEvent.click(within(primaryNav()).getByRole("link", { name: "Sync" }));
    await waitFor(() => expect(document.getElementById("my-work-sync")).toHaveFocus());
    expect(screen.getAllByRole("button", { name: "Sync now" })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Sync now" })).toBeDisabled(); // nothing queued on this device
    expect(screen.getByText("Nothing waiting to send.")).toBeInTheDocument();
  });

  test("a driver who opens an owner section's address keeps their own work and is told why the section is not there", async () => {
    vi.stubGlobal("fetch", memberFetch("driver"));
    renderApp("/workspace?section=customers");
    expect(await screen.findByRole("button", { name: /01.*Corner Shop/ })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("does not have owner permission");
    expect(screen.queryByRole("heading", { name: "Find every matching customer" })).not.toBeInTheDocument();
    expect(railLinks()).toEqual(["My work", "Sync"]);
  });

  test("a suspended business offers no section links: only the workspace entry and the account options", async () => {
    vi.stubGlobal("fetch", memberFetch("owner", "SUSPENDED"));
    renderApp("/workspace");
    expect(await screen.findByText(/This tenant is not active/)).toBeInTheDocument(); // the body shows only the inactive notice
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("North Route");
    expect(railLinks()).toEqual(["Overview"]);
    expect(railLink("Overview")).toHaveAttribute("href", "/workspace");
    expect(within(screen.getByRole("group", { name: "Account" })).getAllByRole("link").map((link) => link.textContent)).toEqual(["Profile", "Public statistics"]);
    expect(primaryLinks()).toEqual(["Overview", "Profile"]);
    fireEvent.click(within(primaryNav()).getByRole("button", { name: "More" }));
    expect(within(moreSheet()).queryByRole("group", { name: "Workspace sections" })).not.toBeInTheDocument();
    expect(within(moreSheet()).getAllByRole("link").map((link) => link.textContent)).toEqual(["Public statistics"]);
    expect(document.querySelectorAll("a[href*='section=']")).toHaveLength(0);
  });

  test("an owner who also drives for another business gets the navigation of the selected business only, through switching and the browser's history", async () => {
    vi.stubGlobal("fetch", mixedFetch());
    renderApp("/workspace");
    expect(await screen.findByRole("heading", { name: "North Route" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /01.*Corner Shop/ })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["Work", "Customers", "Invoices"]);
    expect(businessRole()).toBe("Owner"); // the page heading describes the selected business
    fireEvent.click(screen.getByRole("button", { name: "Mark delivered" }));
    expect(await screen.findByText("1 of 1 completed")).toBeInTheDocument(); // the owner's day meter
    fireEvent.click(within(primaryNav()).getByRole("link", { name: "Customers" }));
    expect(await screen.findByRole("heading", { name: "Find every matching customer" })).toBeInTheDocument();
    expect(within(primaryNav()).getByRole("link", { name: "Customers" })).toHaveAttribute("href", "/workspace?section=customers"); // the first business needs no parameter

    // Switching to the driver business: driver grouping, driver work, and no owner-only section left open.
    fireEvent.change(screen.getByLabelText("Business"), { target: { value: harbour.id } });
    expect(await screen.findByRole("heading", { name: "Harbour Line" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /01.*Harbour Kiosk/ })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["My work", "Sync"]);
    expect(within(primaryNav()).getByRole("link", { name: "My work" })).toHaveAttribute("aria-current", "page");
    expect(within(primaryNav()).getByRole("link", { name: "Sync" })).toHaveAttribute("href", `/workspace?tenant=${harbour.id}#my-work-sync`);
    expect(railLinks()).toEqual(["My work", "Sync"]);
    expect(railLink("My work")).toHaveAttribute("href", `/workspace?tenant=${harbour.id}#my-work`); // the rail keeps the selected business too
    expect(screen.queryByRole("heading", { name: "Find every matching customer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Corner Shop/ })).not.toBeInTheDocument();
    expect(screen.getByText("0 of 1 completed")).toBeInTheDocument(); // the day meter belongs to the selected business
    expect(businessRole()).toBe("Driver"); // the page heading follows the selected business, not the member's other role
    expect(screen.queryByText(/does not have owner permission/)).not.toBeInTheDocument();
    fireEvent.click(within(primaryNav()).getByRole("button", { name: "More" }));
    expect(within(moreSheet()).getAllByRole("link").map((link) => link.textContent)).toEqual(["Profile", "Public statistics"]);
    expect(moreSheet().textContent).not.toMatch(/customers|invoices|deliveries|analytics|branding|backup/i);
    fireEvent.keyDown(document, { key: "Escape" });

    // Back: the owner business returns with the section it had open; the shell follows.
    act(() => { void browserNavigate?.(-1); });
    expect(await screen.findByRole("heading", { name: "Find every matching customer" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "North Route" })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["Work", "Customers", "Invoices"]);
    expect(railLink("Customers")).toHaveAttribute("aria-current", "page");
    expect(businessRole()).toBe("Owner");
    expect(screen.getByLabelText("Business")).toHaveValue(tenant.id);

    // Forward: the driver business again, picker and shell in agreement.
    act(() => { void browserNavigate?.(1); });
    expect(await screen.findByRole("heading", { name: "Harbour Line" })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["My work", "Sync"]);
    expect(screen.getByLabelText("Business")).toHaveValue(harbour.id);
    expect(railLinks()).toEqual(["My work", "Sync"]);

    // Switching back through the picker opens the owner's Work view, not a stale section.
    fireEvent.change(screen.getByLabelText("Business"), { target: { value: tenant.id } });
    expect(await screen.findByRole("heading", { name: "North Route" })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["Work", "Customers", "Invoices"]);
    expect(within(primaryNav()).getByRole("link", { name: "Work" })).toHaveAttribute("aria-current", "page");
    expect(railLink("Work")).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "My route" })).toBeInTheDocument();
  });

  test("a workspace address names the business for the shell and the body alike, and an unknown one falls back to the first for both", async () => {
    vi.stubGlobal("fetch", mixedFetch());
    renderApp(`/workspace?tenant=${harbour.id}`);
    expect(await screen.findByRole("heading", { name: "Harbour Line" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /01.*Harbour Kiosk/ })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["My work", "Sync"]);
    expect(within(primaryNav()).getByRole("link", { name: "My work" })).toHaveAttribute("href", `/workspace?tenant=${harbour.id}#my-work`);
    expect(railLinks()).toEqual(["My work", "Sync"]);
    expect(screen.getByLabelText("Business")).toHaveValue(harbour.id);
    cleanup();

    vi.stubGlobal("fetch", mixedFetch());
    renderApp("/workspace?tenant=99999999-9999-4999-8999-999999999999&section=customers");
    expect(await screen.findByRole("heading", { name: "North Route" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Find every matching customer" })).toBeInTheDocument();
    expect(primaryLinks()).toEqual(["Work", "Customers", "Invoices"]);
    expect(railLink("Customers")).toHaveAttribute("aria-current", "page");
    expect(screen.getByLabelText("Business")).toHaveValue(tenant.id);
    cleanup();

    // An owner business named in the address stays named in every rail section link.
    vi.stubGlobal("fetch", mixedFetch());
    renderApp(`/workspace?tenant=${tenant.id}&section=customers`);
    expect(await screen.findByRole("heading", { name: "Find every matching customer" })).toBeInTheDocument();
    expect(railLink("Invoices")).toHaveAttribute("href", `/workspace?tenant=${tenant.id}&section=invoices`);
    expect(railLink("Work")).toHaveAttribute("href", `/workspace?tenant=${tenant.id}`);
  });
});
