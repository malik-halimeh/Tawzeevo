import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 4 offline flow (PHASE_04.md M/O E2E): download the business, lose the connection, find a
 * customer and scan a product from the device, queue an invoice with a pending reference, come
 * back online, sync once, and see the server-created draft with the same customer and line.
 *
 * Environment: E2E_API_URL (default http://127.0.0.1:8011), E2E_WEB_URL (default
 * http://127.0.0.1:5173), E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for an existing platform admin.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const OWNER_PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-offline-${stamp}@example.com`;
const customerPhone = `+96170${(Date.now() % 1_000_000).toString().padStart(6, "0")}`;
const barcode = `52801${(Date.now() % 100_000_000).toString().padStart(8, "0")}`;
const newCustomerPhone = `+96170${((Date.now() + 3) % 1_000_000).toString().padStart(6, "0")}`;

test("owner keeps invoicing offline and the queued draft is created once on reconnect", async ({ page, context }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };

  // ----- API setup: owner, tenant, catalog, customer -----
  await json(await api.post("/register", { data: { first_name: "Nour", last_name: "Saleh", email: ownerEmail, phone: `+96171${((Date.now() + 11) % 1_000_000).toString().padStart(6, "0")}`, city: "Tripoli", age: 29, password: OWNER_PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: OWNER_PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const admin = { Authorization: `Bearer ${adminToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `E2E Offline Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: admin, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  expect(tenantId).toBeTruthy();
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Dairy", name_ar: "ألبان", slug: `dairy-${stamp}` } }));
  const product = await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Baalbek Labneh", barcode, unit_price: "4.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6 } }));
  const customerId = (await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Rima Grocery", phone: customerPhone, grade: "B+" } }))).id as string;

  // ----- Browser: sign in and download the business for offline use -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await page.getByRole("tab", { name: "Offline" }).click();
  await page.getByRole("button", { name: "Download for offline use" }).click();
  await expect(page.getByRole("button", { name: "Download again" })).toBeVisible();
  await expect(page.getByText(/1 \/ 1 \/ 0/)).toBeVisible();

  // ----- Connection lost: a new customer is created on the device -----
  await context.setOffline(true);
  await expect(page.locator(".status-badge", { hasText: "Offline" })).toBeVisible();
  await page.getByRole("tab", { name: "Customers" }).click();
  await page.getByRole("textbox", { name: "Customer name" }).fill("Offline Corner Shop");
  await page.locator("form.form-grid").getByRole("textbox", { name: "Phone" }).fill(newCustomerPhone);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("No connection: the customer was saved on this device and will be sent once when you are back online.")).toBeVisible();

  // ----- Still offline: search (device projection), scan (device catalog), queue the invoice -----
  await page.getByRole("tab", { name: "Invoices" }).click();
  await page.getByRole("textbox", { name: "Phone", exact: true }).fill(newCustomerPhone);
  await page.getByRole("button", { name: "Search" }).first().click();
  await expect(page.getByText("1 matching record(s) from this device (offline).")).toBeVisible();
  await page.getByRole("button", { name: /Offline Corner Shop/ }).click();
  await page.getByRole("textbox", { name: "Barcode", exact: true }).fill(barcode);
  await page.getByRole("button", { name: "Scan barcode" }).click();
  await expect(page.getByText("Item added from this device's catalog (offline).")).toBeVisible();
  await page.getByRole("button", { name: "Calculate and save draft" }).click();
  await expect(page.getByText(/No connection: the invoice was saved on this device as PENDING-[0-9A-F]{8}/)).toBeVisible();

  // ----- The queued command is visible, never hidden -----
  await page.getByRole("tab", { name: "Offline" }).click();
  await expect(page.getByText("Waiting to send").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Sync now" })).toBeDisabled();

  // ----- Back online: one sync sends it once; the server creates the draft -----
  await context.setOffline(false);
  await expect(page.getByRole("button", { name: "Sync now" })).toBeEnabled();
  await page.getByRole("button", { name: "Sync now" }).click();
  await expect(page.getByText(/Synced: 2 change\(s\) sent/)).toBeVisible();
  await expect(page.getByText("Nothing waiting: every change has been sent and accepted.")).toBeVisible();
  await page.getByRole("button", { name: "Sync now" }).click();
  await expect(page.getByText(/Synced: 0 change\(s\) sent/)).toBeVisible();

  // ----- API: exactly one draft, for that customer, with that line, no official number yet -----
  const device = await page.evaluate(() => localStorage.getItem("tawzeevo.device_installation_id"));
  expect(device).toBeTruthy();
  const bootstrap = await json(await api.post(`/api/v1/sync/bootstrap?tenant_id=${tenantId}`, { headers: owner, data: { device_installation_id: device, protocol_version: 1, app_schema_version: 2 } }));
  expect(bootstrap.device_installation_id ?? device).toBeTruthy();
  const invoices = await json(await api.get(`/api/v1/sync/bootstrap/invoices?tenant_id=${tenantId}&device_installation_id=${String(device)}`, { headers: owner }));
  const rows = invoices.items as Array<Record<string, unknown>>;
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ status: "DRAFT", official_invoice_number: null });
  const customers = await json(await api.get(`/api/v1/sync/bootstrap/customers?tenant_id=${tenantId}&device_installation_id=${String(device)}`, { headers: owner }));
  const created = (customers.items as Array<Record<string, unknown>>).find((row) => row.name === "Offline Corner Shop");
  expect(created, "the offline-created customer exists once on the server").toBeTruthy();
  expect(rows[0]?.customer_id).toBe(created?.id);
  expect((customers.items as Array<Record<string, unknown>>).map((row) => row.id)).toContain(customerId);
  const items = await json(await api.get(`/api/v1/sync/bootstrap/invoice_revision_items?tenant_id=${tenantId}&device_installation_id=${String(device)}`, { headers: owner }));
  const lines = items.items as Array<Record<string, unknown>>;
  expect(lines).toHaveLength(1);
  expect(lines[0]).toMatchObject({ tenant_product_id: product.id, quantity: "1.0000" });
  await api.dispose();
});
