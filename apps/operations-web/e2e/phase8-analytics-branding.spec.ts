import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 8 flow (PHASE_08.md J/E2E): a seeded business's dashboard reconciles with the ledgers
 * and the confirmed invoices; the customer lifetime drilldown shows the same truth; branding
 * saved on the owner desk appears on the storefront (theme, title, logo, banner, info page,
 * default language) and on the customer invoice page (header, terms, thank-you, safe QR) without
 * touching a price.
 *
 * Environment: E2E_API_URL (default http://127.0.0.1:8011), E2E_WEB_URL (operations client,
 * default http://127.0.0.1:5173), E2E_SHOP_URL (storefront, default http://127.0.0.1:3000),
 * E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for an existing platform admin.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const SHOP = process.env.E2E_SHOP_URL ?? "http://127.0.0.1:3000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-p8-${stamp}@example.com`;
const slug = `cedar-${stamp}`;

// A 1x1 red PNG, enough for the validated logo pipeline.
const LOGO_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

test("dashboard reconciles, lifetime drilldown matches, branding renders on storefront and invoice page", async ({ page, browser }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };
  const phone = (n: number) => `+96170${((Date.now() + n) % 1_000_000).toString().padStart(6, "0")}`;

  // ----- API setup: owner, tenant, product with cost, customer, two confirmed invoices, one receipt -----
  await json(await api.post("/register", { data: { first_name: "Nour", last_name: "Cedar", email: ownerEmail, phone: phone(1), city: "Beirut", age: 40, password: PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `Cedar Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: { Authorization: `Bearer ${adminToken}` }, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Water", name_ar: "مياه", slug: `water-${stamp}` } }));
  const product = await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Cedar Water 1.5L", barcode: `62903${(Date.now() % 100_000_000).toString().padStart(8, "0")}`, unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6, is_published: true } }));
  const supplier = await json(await api.post(`/api/v1/suppliers?tenant_id=${tenantId}`, { headers: owner, data: { name: "Cedar Source" } }));
  await json(await api.post(`/api/v1/suppliers/products/${String(product.id)}/costs?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id, unit_cost: "7.0000", currency: "USD", cost_basis: "PIECE" } }));
  await json(await api.put(`/api/v1/tenants/${tenantId}/storefront/slug`, { headers: owner, data: { slug } }));
  const customer = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Maya Market", phone: phone(9), address: "Hamra street" } }));
  const confirm = async (qty: string) => {
    const draft = await json(await api.post(`/api/v1/invoices?tenant_id=${tenantId}`, { headers: owner, data: { client_command_id: crypto.randomUUID(), customer_id: customer.id, currency: "USD", invoice_discount_expression: "0", invoice_markup_expression: "0", items: [{ product_id: product.id, quantity_expression: qty, price_basis: "PIECE", line_discount_expression: "0", line_markup_expression: "0" }] } }));
    return json(await api.post(`/api/v1/invoices/${String(draft.id)}/confirm?tenant_id=${tenantId}`, { headers: owner, data: { expected_revision_id: draft.current_revision_id } }));
  };
  await confirm("2");
  const second = await confirm("3");
  await json(await api.post(`/api/v1/payments/customer-receipts?tenant_id=${tenantId}`, { headers: owner, data: { idempotency_key: crypto.randomUUID(), customer_id: customer.id, amount: "15.0000", currency: "USD", paid_at: new Date().toISOString() } }));

  // ----- Reconciliation through the API: dashboard = ledger truth = invoices -----
  const started = Date.now();
  const overview = await json(await api.get(`/api/v1/analytics/overview?tenant_id=${tenantId}&period=30d`, { headers: owner }));
  const overviewMs = Date.now() - started;
  expect(overviewMs, `analytics overview took ${overviewMs} ms`).toBeLessThan(2_000);
  const usd = (rows: unknown) => (rows as { currency: string; amount: string }[]).find((row) => row.currency === "USD")?.amount;
  expect(usd(overview.invoiced_sales)).toBe("50.0000");
  expect(usd(overview.customer_receipts)).toBe("15.0000");
  expect(usd(overview.customer_outstanding)).toBe("35.0000");
  const balances = await json(await api.get(`/api/v1/customer-ledger/customers/${String(customer.id)}/balances?tenant_id=${tenantId}`, { headers: owner }));
  expect((balances.balances as { currency: string; balance: string }[]).find((row) => row.currency === "USD")?.balance).toBe("35.0000");
  const profit = (overview.gross_profit as { currency: string; gross_profit: string; coverage_percent: string }[]).find((row) => row.currency === "USD");
  expect(profit?.gross_profit).toBe("15.0000"); // (10 - 7) × 5 pieces
  expect(profit?.coverage_percent).toBe("100.0000");

  // ----- Owner in the browser: Analytics tab shows the same figures; lifetime drilldown -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await page.getByRole("tab", { name: "Analytics" }).click();
  const analytics = page.getByRole("region", { name: "Business figures" });
  await expect(analytics.getByText("50.0000 USD").first()).toBeVisible();
  await expect(analytics.getByText("15.0000 USD").first()).toBeVisible();
  await expect(analytics.getByText("35.0000 USD").first()).toBeVisible();
  await expect(analytics.getByRole("table", { name: "Historical gross profit" }).getByRole("cell", { name: "100.0000% (2/2)" })).toBeVisible();
  await analytics.getByLabel("Phone").fill(customer.phone as string);
  await analytics.getByRole("button", { name: "Search" }).click();
  const money = analytics.getByRole("table", { name: "Money by currency" });
  await expect(money).toBeVisible();
  await expect(money.getByRole("cell", { name: "50.0000", exact: true })).toBeVisible(); // purchased
  await expect(money.getByRole("cell", { name: "30.0000", exact: true })).toBeVisible(); // largest
  await expect(money.getByRole("cell", { name: "25.0000", exact: true })).toBeVisible(); // average
  await expect(money.getByRole("cell", { name: "35.0000", exact: true })).toBeVisible(); // outstanding
  await expect(analytics.getByText("Cedar Water 1.5L", { exact: false }).first()).toBeVisible();

  // ----- Owner: branding desk -----
  await page.getByRole("tab", { name: "Branding" }).click();
  const branding = page.getByRole("region", { name: "How your business looks" });
  await branding.getByLabel("Storefront title").fill("Cedar Van Beirut");
  await branding.getByLabel("Homepage banner").fill("Free delivery in Beirut this week");
  await branding.getByLabel("Primary colour (#rrggbb)").fill("#1f6f5f");
  await branding.getByLabel("About", { exact: true }).fill("Family business since 2001.");
  await branding.getByLabel("Invoice header").fill("Cedar Van · Beirut");
  await branding.getByLabel("Invoice terms").fill("Payment within 7 days");
  await branding.getByLabel("Thank-you line").fill("See you next week");
  await branding.getByLabel(/QR code/).check();
  await branding.getByLabel("Default storefront language").selectOption("ar");
  await branding.getByRole("button", { name: "Save changes" }).click();
  await expect(branding.getByText("Branding saved.")).toBeVisible();
  await branding.getByLabel("Upload logo (PNG, JPEG or WebP)").setInputFiles({ name: "logo.png", mimeType: "image/png", buffer: LOGO_PNG });
  await expect(branding.getByText("Logo saved.")).toBeVisible();
  await expect(branding.getByRole("img", { name: /logo/ })).toBeVisible();

  // Branding changed nothing about money: the public price and the dashboard are as before.
  const listed = await json(await api.get(`/api/v1/public/${slug}/catalog/products`));
  expect((listed.items as { price: string }[])[0]?.price).toBe("10.0000");
  const again = await json(await api.get(`/api/v1/analytics/overview?tenant_id=${tenantId}&period=30d`, { headers: owner }));
  expect(usd(again.invoiced_sales)).toBe("50.0000");

  // ----- Storefront: theme, title, logo, banner, info page, default Arabic, visitor override -----
  const shop = await browser.newContext({ baseURL: SHOP, locale: "en-US" });
  const guest = await shop.newPage();
  await guest.goto(`/${slug}`);
  await expect(guest.locator("[dir=rtl][lang=ar]").first()).toBeVisible(); // business default, no visitor choice
  await expect(guest.getByRole("heading", { level: 1 })).toContainText("Cedar Van Beirut");
  await expect(guest.locator("img.shop-logo")).toBeVisible();
  await expect(guest.getByText("Free delivery in Beirut this week")).toBeVisible();
  await expect(guest.locator("[dir=rtl][lang=ar]").first()).toHaveAttribute("style", /--accent:\s*#1f6f5f/); // theme token from the business
  await guest.getByRole("link", { name: "من نحن" }).click();
  await expect(guest.getByText("Family business since 2001.")).toBeVisible();
  await guest.goto(`/${slug}?lang=en`);
  await expect(guest.locator("[dir=ltr][lang=en]").first()).toBeVisible(); // the visitor's choice wins
  await expect(guest.getByRole("link", { name: "About" })).toBeVisible();
  await shop.close();

  // ----- Customer invoice page: header, terms, thank-you, QR of the same page only -----
  const link = await json(await api.post(`/api/v1/invoices/${String(second.id)}/capabilities?tenant_id=${tenantId}`, { headers: owner, data: {} }));
  const secret = (link.public_path as string).split("#")[1] ?? "";
  const invoicePage = await browser.newPage();
  await invoicePage.goto(`${API}/api/v1/public/invoice#${secret}`);
  await expect(invoicePage.getByText("Cedar Van · Beirut")).toBeVisible();
  await expect(invoicePage.locator("html")).toHaveAttribute("dir", "rtl"); // business default language
  await expect(invoicePage.getByText("Payment within 7 days")).toBeVisible();
  await expect(invoicePage.getByText("See you next week")).toBeVisible();
  await expect(invoicePage.locator("#logo")).toBeVisible();
  await expect(invoicePage.locator("#qr")).toHaveAttribute("src", /^blob:/);
  expect(invoicePage.url()).not.toContain(secret); // the secret left the address bar
  const qr = await api.get("/api/v1/public/invoice/qr", { headers: { "X-Invoice-Capability": secret } });
  expect(qr.status()).toBe(200);
  expect(qr.headers()["content-type"]).toBe("image/png");
  expect((await api.get("/api/v1/public/invoice/qr")).status()).toBe(404);
  await invoicePage.close();

  // ----- Public platform stats: aggregate only, withheld for a small cohort -----
  const stats = await json(await api.get("/stats/platform"));
  expect(stats.minimum_businesses).toBe(5);
  if (stats.sufficient_data === false) expect(stats.active_businesses).toBeNull();
  expect(JSON.stringify(stats)).not.toMatch(/revenue|debt|outstanding|tenant_id/i);
  await api.dispose();
});
