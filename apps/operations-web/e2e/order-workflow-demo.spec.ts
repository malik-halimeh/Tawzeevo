import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Order workflow fix — the whole demo path in real browsers (D-090, M1–M4):
 * link for customer X → X orders without typing name/phone → the owner, on another page, sees the
 * Orders badge, the "(1)" tab title and a notice → the order is already X's → confirm → share the
 * invoice (the shared link works signed out and shows only that invoice) → record a payment with the
 * invoice preselected → create a delivery with the invoice preselected → mark delivered → open the
 * invoice from the delivery.
 *
 * Environment: E2E_API_URL, E2E_WEB_URL, E2E_SHOP_URL, E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const SHOP = process.env.E2E_SHOP_URL ?? "http://127.0.0.1:3000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-demo-${stamp}@example.com`;
const slug = `demo-${stamp}`;

test("personalized order → badge and notice → confirm → share → pay → deliver, without re-selecting", async ({ page, browser }) => {
  test.setTimeout(180_000);
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };
  const phone = (n: number) => `+96176${((Date.now() + n) % 1_000_000).toString().padStart(6, "0")}`;

  // ----- Setup: owner, business, one published product with a supplier cost, customer X -----
  await json(await api.post("/register", { data: { first_name: "Rana", last_name: "Demo", email: ownerEmail, phone: phone(1), city: "Beirut", age: 36, password: PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `Demo Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: { Authorization: `Bearer ${adminToken}` }, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Water", name_ar: "مياه", slug: `water-${stamp}` } }));
  const product = await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Demo Water 1.5L", barcode: `62906${(Date.now() % 100_000_000).toString().padStart(8, "0")}`, unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6, is_published: true } }));
  const supplier = await json(await api.post(`/api/v1/suppliers?tenant_id=${tenantId}`, { headers: owner, data: { name: "Demo Distributor" } }));
  await json(await api.post(`/api/v1/suppliers/products/${String(product.id)}/costs?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id, unit_cost: "7.5000", currency: "USD", cost_basis: "PIECE", pieces_per_box: 6 } }));
  await json(await api.put(`/api/v1/suppliers/products/${String(product.id)}/preferred-supplier?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id } }));
  await json(await api.put(`/api/v1/tenants/${tenantId}/storefront/slug`, { headers: owner, data: { slug } }));
  const customer = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Karim Grocery", phone: phone(5), grade: "A", address: "Karim Street 5, Beirut" } }));

  // ----- 1. The owner generates the personalized link for customer X in the workspace -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  const rail = page.getByRole("navigation", { name: "Workspace navigation" });
  await rail.getByRole("link", { name: "Customers", exact: true }).click();
  const finder = page.getByRole("heading", { name: "Find every matching customer" }).locator("..");
  await finder.getByLabel("Phone").fill(customer.phone as string);
  await finder.getByRole("button", { name: "Search" }).click();
  await page.getByRole("list", { name: "Matching customers" }).getByRole("button").first().click();
  await page.getByRole("button", { name: "Storefront link" }).first().click();
  await page.getByRole("button", { name: "Create personalized link" }).click();
  const link = await page.getByLabel("Personalized link").inputValue();
  expect(link).toContain(`/${slug}/access#`);
  const titleBefore = await page.title();
  expect(titleBefore).not.toMatch(/^\(\d+\)/);

  // ----- 2. Customer X orders through the link without typing a name or phone -----
  const shop = await browser.newContext({ locale: "en-US" });
  const buyer = await shop.newPage();
  // The workspace shows the link on its configured storefront address; the test shop may differ.
  await buyer.goto(`${SHOP}${link.slice(link.indexOf(`/${slug}/access#`))}`);
  await expect(buyer.getByText("Prices shown for Karim Grocery.")).toBeVisible();
  await buyer.getByRole("button", { name: "Add to cart" }).first().click();
  await buyer.getByRole("link", { name: /^Cart/ }).first().click();
  await expect(buyer.getByTestId("ordering-as")).toHaveText("Ordering as Karim Grocery");
  await expect(buyer.getByLabel("Name")).toHaveCount(0);
  await expect(buyer.getByLabel("Phone")).toHaveCount(0);
  await expect(buyer.getByText("Leave the address empty to use the delivery address the shop has on file.")).toBeVisible();
  await buyer.getByRole("button", { name: "Place order" }).click();
  await expect(buyer).toHaveURL(new RegExp(`/${slug}/order`));

  // ----- 3. The owner, still on Customers, sees the badge, the "(1)" title and the notice -----
  await expect(rail.getByRole("link", { name: /^Orders/ })).toContainText("1", { timeout: 45_000 });
  await expect(page).toHaveTitle(`(1) ${titleBefore}`);
  const notice = page.getByRole("link", { name: "New order from Karim Grocery" });
  await expect(notice).toBeVisible();

  // ----- 4. The order opens already linked to X; the owner confirms it -----
  await notice.click();
  await expect(page.getByText("Customer: Karim Grocery. Prices are this customer's.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create a new customer from these details" })).toHaveCount(0);
  await page.getByRole("button", { name: "Confirm and assign invoice number" }).click();
  await expect(page.getByText("Order confirmed; the invoice is now official.")).toBeVisible();
  await expect(page).toHaveTitle(titleBefore); // nothing awaits review any more
  const steps = page.getByRole("region", { name: "Next steps" });
  await expect(steps).toBeVisible();
  const orders = (await json(await api.get(`/api/v1/tenants/${tenantId}/orders?tenant_id=${tenantId}`, { headers: owner }))).orders as Record<string, unknown>[];
  expect(orders[0]?.linked_customer_id).toBe(customer.id);
  const detail = await json(await api.get(`/api/v1/tenants/${tenantId}/orders/${String(orders[0]?.id)}?tenant_id=${tenantId}`, { headers: owner }));
  const invoice = detail.invoice as { id: string; official_invoice_number: string; net_sales: string };
  await expect(steps.getByRole("link", { name: invoice.official_invoice_number })).toBeVisible();

  // ----- 5. Share the invoice: the copied link works signed out and shows only this invoice -----
  await steps.getByRole("button", { name: "Manage invoice links" }).click();
  await steps.getByRole("button", { name: "Create private link" }).click();
  const shared = await steps.getByLabel("Private invoice URL").inputValue();
  await expect(steps.getByRole("button", { name: "Copy share link" })).toBeVisible();
  const stranger = await browser.newContext({ locale: "en-US" }); // no session, no cookies
  const publicView = await stranger.newPage();
  await publicView.goto(shared);
  await expect(publicView.getByText(invoice.official_invoice_number).first()).toBeVisible();
  await expect(publicView.getByText(/Karim Grocery/).first()).toBeVisible();
  const publicText = (await publicView.locator("body").innerText()).toLowerCase();
  for (const word of ["supplier", "cost", "grade", "driver"]) expect(publicText).not.toContain(word);
  await publicView.goto("about:blank"); // a fresh load: a fragment-only change would not reload
  await publicView.goto(`${shared.split("#")[0]}#${"0".repeat(32)}.${"A".repeat(43)}`);
  await expect(publicView.getByText(/This link is invalid, expired, revoked, or temporarily unavailable/)).toBeVisible();
  await expect(publicView.getByText(invoice.official_invoice_number)).toHaveCount(0);
  await stranger.close();

  // ----- 6. Record a payment with the invoice preselected -----
  await steps.getByRole("link", { name: "Record payment" }).click();
  const payments = page.getByLabel("Payments");
  await expect(payments.getByText(`Payment for invoice ${invoice.official_invoice_number}: its open amount is selected.`, { exact: false })).toBeVisible();
  await expect.poll(async () => Number(await payments.getByLabel("Amount received").inputValue())).toBe(Number(invoice.net_sales)); // the invoice's open amount
  await payments.getByRole("button", { name: "Record receipt" }).click();
  await expect(page.getByText("Receipt recorded and allocated.")).toBeVisible();
  const obligations = (await json(await api.get(`/api/v1/payments/customers/${String(customer.id)}/obligations?tenant_id=${tenantId}&currency=USD`, { headers: owner }))).obligations as Record<string, unknown>[];
  expect(obligations.find((row) => row.source_id === invoice.id)).toBeUndefined(); // settled

  // ----- 7. Back on the order (resume), create the delivery with the invoice preselected -----
  await rail.getByRole("link", { name: /^Orders/ }).click();
  await page.getByRole("button", { name: /Karim Grocery/ }).click();
  await page.getByRole("region", { name: "Next steps" }).getByRole("link", { name: "Create delivery" }).click();
  await expect(page.getByLabel("Confirmed invoice")).toHaveValue(invoice.id);
  await page.getByRole("button", { name: "Create delivery" }).click();
  await expect(page.getByText("Delivery created.")).toBeVisible();
  await page.getByRole("button", { name: "Mark delivered" }).click();
  await expect(page.getByText("Delivery marked done.")).toBeVisible();

  // ----- 8. The invoice is clickable from the delivery -----
  await page.getByRole("link", { name: `Open invoice ${invoice.official_invoice_number}` }).first().click();
  await expect(page.getByRole("heading", { name: invoice.official_invoice_number })).toBeVisible();
  await expect(page.getByText(/Opened for viewing, sharing and payments/)).toBeVisible();

  await shop.close();
  await api.dispose();
});
