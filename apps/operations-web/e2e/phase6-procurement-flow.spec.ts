import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 6 chain (PHASE_06.md L "Offline/E2E"): confirmed demand → procurement list → actual
 * purchase → supplier payable → payment, in the real owner screens. Supplier profile and price
 * insight are exercised on the way; the driver never appears because a sole owner needs nobody.
 *
 * Environment: E2E_API_URL (default http://127.0.0.1:8011), E2E_WEB_URL (default
 * http://127.0.0.1:5173), E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for an existing platform admin.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const OWNER_PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-buy-${stamp}@example.com`;

test("demand → procurement → purchase → payable → payment", async ({ page }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };

  // ----- API setup: owner, tenant, product, supplier with a cost, one confirmed invoice of 6 -----
  await json(await api.post("/register", { data: { first_name: "Maya", last_name: "Khoury", email: ownerEmail, phone: `+96171${((Date.now() + 9) % 1_000_000).toString().padStart(6, "0")}`, city: "Zahle", age: 31, password: OWNER_PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: OWNER_PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const admin = { Authorization: `Bearer ${adminToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `E2E Buying ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: admin, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Dairy", name_ar: "ألبان", slug: `dairy-${stamp}` } }));
  const product = await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Labneh 500g", barcode: `62901${(Date.now() % 100_000_000).toString().padStart(8, "0")}`, unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6 } }));
  const supplier = await json(await api.post(`/api/v1/suppliers?tenant_id=${tenantId}`, { headers: owner, data: { name: "Bekaa Dairy", contact_phone: "03 123 456", address: "Zahle" } }));
  await json(await api.post(`/api/v1/suppliers/products/${String(product.id)}/costs?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id, unit_cost: "7.0000", currency: "USD", cost_basis: "PIECE" } }));
  const customer = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Corner Shop", phone: `+96170${(Date.now() % 1_000_000).toString().padStart(6, "0")}` } }));
  const draft = await json(await api.post(`/api/v1/invoices?tenant_id=${tenantId}`, { headers: owner, data: { client_command_id: crypto.randomUUID(), customer_id: customer.id, currency: "USD", invoice_discount_expression: "0", invoice_markup_expression: "0", items: [{ product_id: product.id, quantity_expression: "6", price_basis: "PIECE", line_discount_expression: "0", line_markup_expression: "0" }] } }));
  await json(await api.post(`/api/v1/invoices/${String(draft.id)}/confirm?tenant_id=${tenantId}`, { headers: owner, data: { expected_revision_id: draft.current_revision_id } }));

  // ----- Owner: build the list from today's confirmed demand -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await page.getByRole("tab", { name: "Procurement" }).click();
  await page.getByRole("button", { name: "Build from confirmed demand" }).click();
  await expect(page.getByText("List built from confirmed demand.")).toBeVisible();
  const table = page.getByRole("table").first();
  await expect(table.getByText("Labneh 500g")).toBeVisible();
  await expect(table.getByText("6.0000").first()).toBeVisible(); // required = demand
  await expect(page.getByText(/42\.0000 USD/).first()).toBeVisible(); // labelled estimate 6 × 7
  await expect(page.getByText(/stock/i)).toHaveCount(1); // only the sentence saying there is none

  // Sole owner assigns the list to themself.
  await page.getByLabel("Assigned to").selectOption({ index: 1 });
  await expect(page.getByText("Assignee saved.")).toBeVisible();

  // ----- Owner: record the purchase against the list (4 of 6 at 7.20) -----
  await page.getByRole("tab", { name: "Suppliers & costs" }).click();
  const form = page.getByRole("form", { name: "Record purchase" });
  await form.getByRole("combobox", { name: "Supplier", exact: true }).selectOption({ label: "Bekaa Dairy" });
  await form.getByLabel("Procurement list (optional)").selectOption({ index: 1 });
  await expect(form.getByLabel("Line 1 quantity")).toHaveValue("6.0000"); // preloaded remaining
  await form.getByLabel("Line 1 quantity").fill("4");
  await form.getByLabel("Line 1 unit cost").fill("7.2");
  await form.getByRole("button", { name: "Record purchase" }).click();
  await expect(page.getByText("Purchase recorded: 28.8000 USD added to the supplier payable.")).toBeVisible();
  await expect(page.getByText("Owed to suppliers · USD")).toBeVisible();
  await expect(page.getByText("28.8000").first()).toBeVisible();

  // Price insight now shows the actual purchase as last purchase.
  await page.getByRole("combobox", { name: "Product", exact: true }).selectOption({ label: "Labneh 500g · 10.0000 USD" });
  await expect(page.getByRole("table", { name: "Price insight per supplier" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Price insight per supplier" }).getByRole("cell", { name: /Actual purchase/ })).toBeVisible();

  // ----- Procurement progress: 4 purchased, 2 remaining, partly purchased -----
  await page.getByRole("tab", { name: "Procurement" }).click();
  await page.getByRole("button", { name: /Procurement .*/ }).first().click();
  await expect(page.getByText("Partly purchased").first()).toBeVisible();
  await expect(page.getByRole("table").first().getByText("4.0000")).toBeVisible();
  await expect(page.getByRole("table").first().getByText("2.0000")).toBeVisible();

  // ----- Pay the supplier: capped at the payable, then a valid payment -----
  await page.getByRole("tab", { name: "Suppliers & costs" }).click();
  const ledger = page.locator(".supplier-ledger");
  await ledger.getByRole("combobox", { name: "Supplier" }).selectOption({ label: "Bekaa Dairy" });
  await expect(ledger.getByText("28.8000")).toBeVisible();
  await ledger.getByRole("spinbutton", { name: "Payment amount" }).fill("50");
  await ledger.getByRole("button", { name: "Record payment" }).click();
  await expect(page.getByRole("alert").first()).toBeVisible(); // over the payable → refused (D-039)
  await ledger.getByRole("spinbutton", { name: "Payment amount" }).fill("10");
  await ledger.getByRole("button", { name: "Record payment" }).click();
  await expect(ledger.getByText("18.8000")).toBeVisible();

  // The API agrees: payable 18.8 USD, nothing summed across currencies.
  const totals = await json(await api.get(`/api/v1/supplier-ledger/totals?tenant_id=${tenantId}`, { headers: owner }));
  expect(totals.suppliers).toEqual([{ currency: "USD", outstanding: "18.8000", credit: "0.0000", parties: 1 }]);
});
