import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Phase 9 P9-M5 (D-072/D-073): a business that asks for VERIFIED customers. The personalized
 * link alone shows public prices and offers verification; the one-time code (development
 * adapter) grants a verified session and the customer's prices; a wrong code is refused; the
 * owner can end the session from the desk.
 *
 * Environment: E2E_API_URL, E2E_WEB_URL, E2E_SHOP_URL, E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const SHOP = process.env.E2E_SHOP_URL ?? "http://127.0.0.1:3000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-p9v-${stamp}@example.com`;
const slug = `verify-${stamp}`;

test("VERIFIED policy: link offers verification, the code unlocks prices, the owner can end the session", async ({ page, browser }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };
  const phone = (n: number) => `+96170${((Date.now() + n) % 1_000_000).toString().padStart(6, "0")}`;

  // ----- API setup: owner, tenant, published product, grade-A customer with 20 % discount -----
  await json(await api.post("/register", { data: { first_name: "Hala", last_name: "Verify", email: ownerEmail, phone: phone(1), city: "Tripoli", age: 38, password: PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `Verify Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: { Authorization: `Bearer ${adminToken}` }, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Water", name_ar: "مياه", slug: `water-${stamp}` } }));
  await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name: "Verified Water 1.5L", barcode: `62904${(Date.now() % 100_000_000).toString().padStart(8, "0")}`, unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6, is_published: true } }));
  await json(await api.put(`/api/v1/tenants/${tenantId}/grade-discounts/A`, { headers: owner, data: { discount_percent: "20.00" } }));
  await json(await api.put(`/api/v1/tenants/${tenantId}/storefront/slug`, { headers: owner, data: { slug } }));
  await json(await api.put(`/api/v1/tenants/${tenantId}/storefront/access-policy`, { headers: owner, data: { policy: "VERIFIED" } }));
  const customer = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Verified Buyer", phone: phone(9), grade: "A" } }));
  const link = await json(await api.post(`/api/v1/tenants/${tenantId}/customers/${String(customer.id)}/access-link`, { headers: owner, data: {} }));
  const secret = (link.storefront_path as string).split("#")[1] ?? "";

  // ----- Storefront: the link lands on the verification offer, prices stay public -----
  const shop = await browser.newContext({ baseURL: SHOP, locale: "en-US" });
  const guest = await shop.newPage();
  await guest.goto(`/${slug}/access#${secret}`);
  await expect(guest).toHaveURL(new RegExp(`/${slug}/verify`));
  await expect(guest.getByRole("heading", { name: /Confirm it is you, Verified Buyer/ })).toBeVisible();
  await guest.goto(`/${slug}`);
  await expect(guest.getByText(/asks you to confirm your phone/)).toBeVisible();
  await expect(guest.getByText("10.00", { exact: false }).first()).toBeVisible(); // public price

  // ----- Send the code (dev adapter), wrong code refused, right code accepted -----
  await guest.getByRole("link", { name: "Verify now" }).click();
  await guest.getByRole("button", { name: "Send me the code" }).click();
  await expect(guest.getByText(/Code sent to the phone ending in/)).toBeVisible();
  const code = (await (await api.get("/api/v1/public/customer-verification/dev-code", { headers: { "X-Customer-Capability": secret } })).json()) as { code: string };
  await guest.getByLabel("6-digit code").fill("000000");
  await guest.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(guest.getByRole("alert").filter({ hasText: "wrong or no longer valid" })).toBeVisible();
  await guest.getByLabel("6-digit code").fill(code.code);
  await guest.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(guest).toHaveURL(new RegExp(`/${slug}([?]c=[a-f0-9]{24})?$`)); // the tab keeps its link context (D-090)
  await expect(guest.getByText("Prices shown for Verified Buyer.")).toBeVisible();
  await expect(guest.getByText("8.00", { exact: false }).first()).toBeVisible(); // 20 % off, personalized

  // ----- Owner desk: the customer shows one verified session; ending it drops the prices -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  await page.getByRole("navigation", { name: "Workspace navigation" }).getByRole("link", { name: "Customers", exact: true }).click();
  const finder = page.getByRole("heading", { name: "Find every matching customer" }).locator("..");
  await finder.getByLabel("Phone").fill(customer.phone as string);
  await finder.getByRole("button", { name: "Search" }).click();
  await page.getByRole("list", { name: "Matching customers" }).getByRole("button").first().click();
  await page.getByRole("button", { name: "Storefront link" }).first().click();
  const linkBox = page.getByLabel("Personalized storefront link");
  await expect(linkBox.getByText(/1 verified session/)).toBeVisible();
  await linkBox.getByRole("button", { name: "End verified sessions" }).click();
  await expect(linkBox.getByText(/0 verified session/)).toBeVisible();
  await guest.reload();
  await expect(guest.getByText(/asks you to confirm your phone/)).toBeVisible();
  await expect(guest.getByText("10.00", { exact: false }).first()).toBeVisible();
  await shop.close();
  await api.dispose();
});
