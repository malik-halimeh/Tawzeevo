import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 5 storefront flow (PHASE_05.md E2E): a guest browses the public shop, checks out, sees the
 * safe provisional page; the owner links the customer explicitly, confirms through the invoice
 * engine, sets the delivery date; the customer sees it and asks to cancel; the owner decides.
 *
 * Environment: E2E_API_URL (default http://127.0.0.1:8011), E2E_WEB_URL (operations client,
 * default http://127.0.0.1:5173), E2E_SHOP_URL (storefront, default http://127.0.0.1:3000),
 * E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD for an existing platform admin.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const SHOP = process.env.E2E_SHOP_URL ?? "http://127.0.0.1:3000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const OWNER_PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-shop-${stamp}@example.com`;
const slug = `shop-${stamp}`;
const guestPhone = `+96170${(Date.now() % 1_000_000).toString().padStart(6, "0")}`;

test("guest checkout → owner link, confirm, delivery date → customer cancellation request → owner decision", async ({ page, browser }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };

  // ----- API setup: owner, tenant, one published product, storefront slug -----
  await json(await api.post("/register", { data: { first_name: "Layla", last_name: "Haddad", email: ownerEmail, phone: `+96171${((Date.now() + 7) % 1_000_000).toString().padStart(6, "0")}`, city: "Saida", age: 33, password: OWNER_PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: OWNER_PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const admin = { Authorization: `Bearer ${adminToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `E2E Shop ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: admin, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Water", name_ar: "مياه", slug: `water-${stamp}` } }));
  const product = await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Sannine Water 1.5L", barcode: `62900${(Date.now() % 100_000_000).toString().padStart(8, "0")}`, unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6, is_published: true } }));
  // Phase 3 rule: a confirmed line needs a supplier cost snapshot, so the product gets one.
  const supplier = await json(await api.post(`/api/v1/suppliers?tenant_id=${tenantId}`, { headers: owner, data: { name: "Sannine Distributor" } }));
  await json(await api.post(`/api/v1/suppliers/products/${String(product.id)}/costs?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id, unit_cost: "7.5000", currency: "USD", cost_basis: "PIECE", pieces_per_box: 6 } }));
  await json(await api.put(`/api/v1/suppliers/products/${String(product.id)}/preferred-supplier?tenant_id=${tenantId}`, { headers: owner, data: { supplier_id: supplier.id } }));
  await json(await api.put(`/api/v1/tenants/${tenantId}/storefront/slug`, { headers: owner, data: { slug } }));

  // ----- Guest: browse, add to cart, check out -----
  const shop = await browser.newContext({ baseURL: SHOP, locale: "en-US" });
  const guest = await shop.newPage();
  await guest.goto(`/${slug}`);
  await expect(guest.getByText("Sannine Water 1.5L").first()).toBeVisible();
  await guest.getByRole("button", { name: "Add to cart" }).first().click();
  await guest.goto(`/${slug}/cart`);
  await guest.getByLabel("Name").fill("Guest Buyer");
  await guest.getByLabel("Phone").fill(guestPhone);
  await guest.getByLabel("Delivery address").fill("Main street 4, Saida");
  await guest.getByRole("button", { name: "Place order" }).click();
  await expect(guest).toHaveURL(new RegExp(`/${slug}/order`));
  await expect(guest.getByText("Received — the shop will review it and confirm.")).toBeVisible();
  expect(guest.url()).not.toContain("#"); // the reference never stays in the address bar
  const provisional = await guest.locator("main").innerText();
  for (const word of ["grade", "debt", "cost", "supplier", "driver"]) expect(provisional.toLowerCase()).not.toContain(word);

  // ----- Owner: inbox → explicit link (create from the snapshot) → confirm → delivery date -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Orders", exact: true }).click();
  await expect(page.getByText("1 new")).toBeVisible();
  await page.getByRole("button", { name: /Guest Buyer/ }).click();
  await expect(page.getByRole("button", { name: "Confirm and assign invoice number" })).toBeDisabled();
  await page.getByRole("button", { name: "Create a new customer from these details" }).click();
  await expect(page.getByText("Customer linked and the draft repriced.")).toBeVisible();
  await page.getByRole("button", { name: "Confirm and assign invoice number" }).click();
  await expect(page.getByText("Order confirmed; the invoice is now official.")).toBeVisible();
  const tomorrow = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
  await page.getByLabel("Delivery date").fill(tomorrow);
  await page.getByRole("button", { name: "Save delivery date" }).click();
  await expect(page.getByText("Delivery date saved and the reminder scheduled.")).toBeVisible();

  // ----- Customer: revisits the provisional page, sees the date, asks to cancel -----
  await guest.reload();
  await expect(guest.getByText("Confirmed by the shop.")).toBeVisible();
  await expect(guest.getByText(`Planned delivery: ${tomorrow}`)).toBeVisible();
  await guest.getByLabel("Reason (optional)").fill("Ordered twice by mistake");
  await guest.getByRole("button", { name: "Ask the shop to cancel this order" }).click();
  await expect(guest.getByText("Cancellation requested — waiting for the shop.")).toBeVisible();

  // ----- Owner: decides the request; the customer sees the outcome -----
  await page.getByRole("button", { name: /Guest Buyer/ }).click();
  await expect(page.getByText(/Ordered twice by mistake/)).toBeVisible();
  await page.getByRole("button", { name: "Approve cancellation" }).click();
  await expect(page.getByText("Cancellation approved; the sale was reversed.")).toBeVisible();
  await guest.reload();
  await expect(guest.getByText("Cancelled.")).toBeVisible();

  // ----- Public catalog never exposes private data; private pages are no-store -----
  const catalog = await api.get(`/api/v1/public/${slug}/catalog/products`);
  expect((await catalog.text()).toLowerCase()).not.toMatch(/grade|debt|cost_price|supplier|driver/);
  const order = await api.get("/api/v1/public/order", { headers: { "X-Order-Reference": `${"0".repeat(32)}.${"A".repeat(43)}` } });
  expect(order.status()).toBe(404);
  expect(order.headers()["cache-control"]).toContain("no-store");
  await shop.close();
});

test("storefront in Arabic on a phone: RTL layout, cart and order page are usable", async ({ browser }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const catalog = await api.get(`/api/v1/public/${slug}/catalog`);
  test.skip(!catalog.ok(), "needs the shop created by the first test");
  const shop = await browser.newContext({ baseURL: SHOP, locale: "ar", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const guest = await shop.newPage();
  await guest.goto(`/${slug}?lang=ar`);
  await expect(guest.locator("[dir=rtl][lang=ar]").first()).toBeVisible();
  const scroll = await guest.evaluate<number>("document.documentElement.scrollWidth - document.documentElement.clientWidth");
  expect(scroll).toBeLessThanOrEqual(1); // no horizontal overflow on a phone
  await guest.getByRole("button", { name: "أضف إلى السلة" }).first().click();
  await guest.goto(`/${slug}/cart?lang=ar`);
  await expect(guest.getByLabel("الاسم")).toBeVisible();
  await expect(guest.getByRole("button", { name: "إرسال الطلب" })).toBeVisible();
  await guest.getByLabel("الاسم").fill("زبون");
  await guest.getByLabel("الهاتف").fill(`+96171${((Date.now() + 5) % 1_000_000).toString().padStart(6, "0")}`);
  await guest.getByLabel("عنوان التوصيل").fill("صيدا، الشارع الرئيسي");
  await guest.getByRole("button", { name: "إرسال الطلب" }).click();
  await expect(guest).toHaveURL(new RegExp(`/${slug}/order`));
  await expect(guest.getByText("تم الاستلام — سيراجعه المتجر ويؤكده.")).toBeVisible();
  await expect(guest.getByRole("button", { name: "اطلب من المتجر إلغاء هذا الطلب" })).toBeVisible();
  await shop.close();
});
