import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 3 critical flow (PHASE_03.md N E2E): supplier/cost setup -> invoice create -> confirm ->
 * receipt, driven through the real browser against the real API and a disposable PostgreSQL.
 *
 * Environment: E2E_API_URL (default http://127.0.0.1:8011), E2E_WEB_URL (default
 * http://127.0.0.1:5173), E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for an existing platform admin.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const OWNER_PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-${stamp}@example.com`;
const customerPhone = `+96170${(Date.now() % 1_000_000).toString().padStart(6, "0")}`;
const barcode = `52800${(Date.now() % 100_000_000).toString().padStart(8, "0")}`;

test("owner sets up a supplier cost, confirms an invoice and records a receipt", async ({ page }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };

  // ----- API setup: owner account, tenant approval, catalog and customer -----
  await json(await api.post("/register", { data: { first_name: "Rana", last_name: "Khoury", email: ownerEmail, phone: `+96171${((Date.now() + 7) % 1_000_000).toString().padStart(6, "0")}`, city: "Beirut", age: 32, password: OWNER_PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: OWNER_PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const admin = { Authorization: `Bearer ${adminToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `E2E Cash Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: admin, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  expect(tenantId).toBeTruthy();
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Beverages", name_ar: "مشروبات", slug: `bev-${stamp}` } }));
  await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Cedar Sparkling Water", barcode, unit_price: "12.5000", currency: "USD", price_basis: "PIECE", pieces_per_box: 12 } }));
  const customerId = (await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Maya Market", phone: customerPhone, grade: "A" } }))).id as string;

  // ----- Browser: sign in -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);

  // ----- Browser: supplier and cost setup (D-041) -----
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Suppliers & costs", exact: true }).click();
  await page.getByRole("textbox", { name: "Supplier name" }).fill("Bekaa Wholesale");
  await page.getByRole("button", { name: "Add supplier" }).click();
  await expect(page.getByText("Supplier created.")).toBeVisible();
  await page.getByRole("combobox", { name: "Product", exact: true }).selectOption({ label: "Cedar Sparkling Water · 12.5000 USD" });
  await expect(page.getByText("No cost entries for this product yet.")).toBeVisible();
  await page.getByRole("combobox", { name: "Supplier", exact: true }).first().selectOption({ label: "Bekaa Wholesale" });
  await page.getByRole("spinbutton", { name: "Unit cost (USD)" }).fill("8");
  await page.getByRole("button", { name: "Save new cost entry" }).click();
  await expect(page.getByText("Cost entry saved. The invoice editor will preload it.")).toBeVisible();
  await expect(page.getByText("Bekaa Wholesale · preferred").first()).toBeVisible();

  // ----- Browser: supplier ledger desk (D-039 cap and explicit prepayment) -----
  const ledger = page.getByRole("article", { name: "Supplier payable and payments" });
  await ledger.getByRole("combobox", { name: "Supplier", exact: true }).selectOption({ label: "Bekaa Wholesale" });
  await ledger.getByRole("spinbutton", { name: /Opening payable/ }).fill("20");
  await ledger.getByRole("button", { name: "Record opening" }).click();
  await expect(ledger.getByText("Supplier opening balance recorded.")).toBeVisible();
  await expect(ledger.getByText("20.0000")).toBeVisible();
  await ledger.getByRole("spinbutton", { name: "Payment amount" }).fill("25");
  await ledger.getByRole("button", { name: "Record payment", exact: true }).click();
  await expect(ledger.getByRole("alert").filter({ hasText: /cannot exceed the current payable/ })).toBeVisible(); // the refusal itself, not the explanatory body text
  await ledger.getByRole("button", { name: "Record as prepayment" }).click();
  await expect(ledger.getByText("Supplier prepayment recorded as credit.")).toBeVisible();
  await expect(ledger.getByText("-5.0000")).toBeVisible();

  // ----- Browser: invoice create -> confirm -----
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Invoices", exact: true }).click();
  // The section renders after the address changes; wait for it before using its fields.
  await expect(page.getByRole("heading", { name: "Invoices", level: 3 })).toBeVisible();
  await page.getByRole("textbox", { name: "Phone", exact: true }).fill(customerPhone);
  await page.getByRole("button", { name: "Search" }).first().click();
  await page.getByRole("button", { name: /Maya Market/ }).click();
  await page.getByRole("textbox", { name: "Barcode", exact: true }).fill(barcode);
  await page.getByRole("button", { name: "Scan barcode" }).click();
  await expect(page.getByText("Catalog item added.")).toBeVisible();
  await page.getByRole("button", { name: "Calculate and save draft" }).click();
  await expect(page.getByText("Draft invoice created from the server calculation.")).toBeVisible();
  await page.getByRole("button", { name: "Confirm and assign invoice number" }).click();
  await expect(page.getByText(/Invoice \d{4}-\d{6} confirmed and posted to the customer ledger\./)).toBeVisible();

  // ----- Browser: receipt (the Payments view of the Invoices section) -----
  await page.getByRole("group", { name: "Invoice views" }).getByRole("button", { name: "Payments", exact: true }).click();
  await page.getByRole("spinbutton", { name: "Amount received" }).fill("5");
  await page.getByRole("button", { name: "Record receipt" }).click();
  await expect(page.getByText("Receipt recorded and allocated.")).toBeVisible();

  // ----- Browser: sharing is confirmed-only; cancellation revokes; Arabic/RTL renders -----
  await page.getByRole("group", { name: "Invoice views" }).getByRole("button", { name: "Invoice", exact: true }).click();
  await page.getByRole("button", { name: "Manage invoice links" }).click();
  await page.getByRole("button", { name: "Create private link" }).click();
  const publicUrl = await page.getByLabel("Private invoice URL").inputValue();
  expect(publicUrl).toContain("/api/v1/public/invoice#");
  const secret = publicUrl.split("#")[1];
  const publicView = await api.get("/api/v1/public/invoice/data", { headers: { "X-Invoice-Capability": secret } });
  expect(publicView.status()).toBe(200);
  expect(publicView.headers()["cache-control"]).toBe("no-store");
  const projection = (await publicView.json()) as Record<string, unknown>;
  expect(projection.status).toBe("CONFIRMED");
  expect(JSON.stringify(projection)).not.toMatch(/unit_cost|profit|balance|grade/);

  await page.getByRole("button", { name: "العربية" }).first().click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("navigation", { name: "التنقل في مساحة العمل" }).getByRole("link", { name: "الفواتير", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English" }).first().click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

  await page.getByLabel("Cancellation reason").fill("Customer withdrew the order");
  await page.getByRole("button", { name: "Cancel invoice" }).click();
  await expect(page.getByText("Invoice cancelled. Payments were preserved and allocations were released as credit.")).toBeVisible();
  expect((await api.get("/api/v1/public/invoice/data", { headers: { "X-Invoice-Capability": secret } })).status()).toBe(404);

  // ----- API: verify the financial truth behind the UI -----
  const balances = await json(await api.get(`/api/v1/customer-ledger/debts?tenant_id=${tenantId}`, { headers: owner }));
  const debts = balances.debts as Array<Record<string, unknown>>;
  // After cancellation the 12.5 charge is reversed and the 5 receipt remains as credit: no positive debt.
  expect(debts).toHaveLength(0);
  const customerLedger = await json(await api.get(`/api/v1/customer-ledger/customers/${customerId}/balances?tenant_id=${tenantId}`, { headers: owner }));
  expect(customerLedger.balances).toEqual([{ currency: "USD", balance: "-5.0000" }]);
  await api.dispose();
});
