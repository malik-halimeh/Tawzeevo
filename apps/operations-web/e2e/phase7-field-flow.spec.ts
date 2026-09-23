import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 7 field flow (PHASE_07.md L): a sole owner creates and completes their own delivery; a
 * driver is added, gets one assigned stop in a price-free "My Work", suggests a stop order,
 * completes a stop offline (queued, sent once on reconnect), and loses access when revoked.
 *
 * Environment: E2E_API_URL (default http://127.0.0.1:8011), E2E_WEB_URL (default
 * http://127.0.0.1:5173), E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for an existing platform admin.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-field-${stamp}@example.com`;
const driverEmail = `driver-field-${stamp}@example.com`;

test("sole owner delivers; a driver gets assigned-only, price-free work, completes offline and is revoked", async ({ page, browser }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };
  const phone = (n: number) => `+96170${((Date.now() + n) % 1_000_000).toString().padStart(6, "0")}`;

  // ----- API setup: owner, tenant, product with cost, two customers with coordinates, two confirmed invoices -----
  await json(await api.post("/register", { data: { first_name: "Rana", last_name: "Saad", email: ownerEmail, phone: phone(1), city: "Beirut", age: 35, password: PASSWORD } }));
  await json(await api.post("/register", { data: { first_name: "Karim", last_name: "Driver", email: driverEmail, phone: phone(2), city: "Beirut", age: 27, password: PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `E2E Field ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: { Authorization: `Bearer ${adminToken}` }, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Water", name_ar: "مياه", slug: `water-${stamp}` } }));
  const product = await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Sannine 1.5L", barcode: `62902${(Date.now() % 100_000_000).toString().padStart(8, "0")}`, unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6 } }));
  const supplier = await json(await api.post(`/api/v1/suppliers?tenant_id=${tenantId}`, { headers: owner, data: { name: "Sannine Source" } }));
  await json(await api.post(`/api/v1/suppliers/products/${String(product.id)}/costs?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id, unit_cost: "7.0000", currency: "USD", cost_basis: "PIECE" } }));
  const confirmFor = async (name: string, lat: string, lng: string, qty: string) => {
    const customer = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name, phone: phone(name.length * 7), address: `${name} street`, latitude: lat, longitude: lng } }));
    const draft = await json(await api.post(`/api/v1/invoices?tenant_id=${tenantId}`, { headers: owner, data: { client_command_id: crypto.randomUUID(), customer_id: customer.id, currency: "USD", invoice_discount_expression: "0", invoice_markup_expression: "0", items: [{ product_id: product.id, quantity_expression: qty, price_basis: "PIECE", line_discount_expression: "0", line_markup_expression: "0" }] } }));
    return json(await api.post(`/api/v1/invoices/${String(draft.id)}/confirm?tenant_id=${tenantId}`, { headers: owner, data: { expected_revision_id: draft.current_revision_id } }));
  };
  await confirmFor("Hamra Grocer", "33.895000", "35.480000", "2");
  await confirmFor("Achrafieh Market", "33.888000", "35.520000", "3");

  // ----- Owner: sole operator, "My deliveries", creates and completes a delivery -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Deliveries", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My deliveries", level: 3 })).toBeVisible();
  await expect(page.getByLabel("Deliver by")).toHaveCount(0); // no driver setup demanded
  const pickInvoice = async (customer: string) => {
    const value = await page.getByLabel("Confirmed invoice").locator("option", { hasText: customer }).getAttribute("value");
    await page.getByLabel("Confirmed invoice").selectOption(value ?? "");
  };
  await pickInvoice("Hamra Grocer");
  await page.getByRole("button", { name: "Create delivery" }).click();
  await expect(page.getByText("Delivery created.")).toBeVisible();
  await page.getByRole("button", { name: "Mark delivered" }).first().click();
  await expect(page.getByText("Delivery marked done.")).toBeVisible();

  // ----- Owner adds a driver; the business is no longer a sole operation -----
  await page.getByText("Team (drivers)").click();
  await page.getByLabel("Driver's account e-mail").fill(driverEmail);
  await page.getByRole("button", { name: "Add driver" }).click();
  await expect(page.getByText("Driver added.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Deliveries", level: 3 })).toBeVisible();
  await pickInvoice("Achrafieh Market");
  const driverOption = await page.getByLabel("Deliver by").locator("option", { hasText: "Karim Driver" }).getAttribute("value");
  await page.getByLabel("Deliver by").selectOption(driverOption ?? "");
  await page.getByRole("button", { name: "Create delivery" }).click();
  await expect(page.getByText("Delivery created.")).toBeVisible();

  // ----- Driver: My Work shows only the assigned stop, no prices; suggests an order; completes offline -----
  const driverContext = await browser.newContext({ baseURL: process.env.E2E_WEB_URL ?? "http://127.0.0.1:5173", locale: "en-US" });
  const driver = await driverContext.newPage();
  await driver.goto("/login");
  await driver.getByLabel("Email").fill(driverEmail);
  await driver.getByLabel("Password").fill(PASSWORD);
  await driver.getByRole("button", { name: "Sign in" }).click();
  await expect(driver).toHaveURL(/\/workspace/);
  await expect(driver.getByRole("heading", { name: "My route", level: 3 })).toBeVisible();
  await expect(driver.getByText("Achrafieh Market", { exact: true }).first()).toBeVisible(); // the stop list and the selected-stop detail both name it
  await expect(driver.getByText("Hamra Grocer", { exact: true })).toHaveCount(0); // not theirs (already delivered by the owner)
  await expect(driver.getByRole("link", { name: "Suppliers & costs" })).toHaveCount(0);
  const workText = await driver.locator(".my-work").innerText();
  expect(workText.toLowerCase()).not.toMatch(/cost|margin|profit|supplier price/);
  expect(workText).toContain("30.0000 USD"); // amount to collect
  await driver.getByRole("button", { name: "Suggest stop order" }).click();
  await expect(driver.getByText(/stop-order suggestion|Road route/)).toBeVisible();

  await driverContext.setOffline(true);
  await driver.getByRole("button", { name: "Mark delivered" }).click();
  await expect(driver.getByText(/No connection: the completion is saved on this device/)).toBeVisible();
  await driverContext.setOffline(false);
  await driver.getByRole("button", { name: "Sync now" }).click();
  await expect(driver.getByText("Sent.")).toBeVisible();
  await expect(driver.locator(".my-work").getByText("Nothing assigned to you right now.")).toBeVisible();
  const finished = await json(await api.get(`/api/v1/delivery-tasks?tenant_id=${tenantId}&status=COMPLETED`, { headers: owner }));
  expect((finished.tasks as Record<string, unknown>[]).length).toBe(2);
  const byDriver = (finished.tasks as { customer_name: string; performed_by: { role: string } }[]).find((t) => t.customer_name === "Achrafieh Market");
  expect(byDriver?.performed_by.role).toBe("driver");

  // ----- Owner revokes the driver; the driver's next contact is refused -----
  if (!(await page.getByRole("button", { name: "Revoke" }).isVisible())) await page.getByText("Team (drivers)").click();
  await page.getByRole("button", { name: "Revoke" }).click();
  await expect(page.getByText("Membership revoked.")).toBeVisible();
  const refused = await api.get(`/api/v1/delivery-tasks/my-work?tenant_id=${tenantId}`, { headers: { Authorization: `Bearer ${(await json(await api.post("/login", { data: { email: driverEmail, password: PASSWORD } }))).access_token as string}` } });
  expect(refused.status()).toBe(403);
  await driverContext.close();
});
