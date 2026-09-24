import { type Page, expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * D-090: two customers' personalized storefronts open side by side in two tabs of ONE browser
 * context (shared cookies and storage — not separate browsers). Neither tab changes the other's
 * customer, cart or checkout, and each submitted order belongs to its own link's customer.
 *
 * Environment: E2E_API_URL, E2E_SHOP_URL, E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const SHOP = process.env.E2E_SHOP_URL ?? "http://127.0.0.1:3000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-iso-${stamp}@example.com`;
const slug = `iso-${stamp}`;

async function addProduct(tab: Page, name: string) {
  await tab.getByRole("listitem").filter({ hasText: name }).getByRole("button", { name: "Add to cart" }).click();
}

async function cartLines(tab: Page): Promise<string[]> {
  await tab.getByRole("link", { name: /^Cart/ }).first().click();
  await expect(tab.getByRole("heading", { name: "Your details" })).toBeVisible();
  return (await tab.getByRole("list", { name: "Cart" }).locator("li .name").allTextContents()).map((text) => text.trim());
}

test("two personalized customers in two tabs of one browser stay separate through checkout", async ({ browser }) => {
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };
  const phone = (n: number) => `+96171${((Date.now() + n) % 1_000_000).toString().padStart(6, "0")}`;

  await json(await api.post("/register", { data: { first_name: "Iso", last_name: "Owner", email: ownerEmail, phone: phone(1), city: "Beirut", age: 40, password: PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `Iso Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: { Authorization: `Bearer ${adminToken}` }, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  const category = await json(await api.post(`/api/v1/tenants/${tenantId}/categories`, { headers: owner, data: { name_en: "Grocery", name_ar: "بقالة", slug: `grocery-${stamp}` } }));
  const barcode = (n: number) => `62905${((Date.now() + n) % 100_000_000).toString().padStart(8, "0")}`;
  for (const [index, name] of ["Iso Water", "Iso Rice"].entries()) {
    await json(await api.post(`/api/v1/tenants/${tenantId}/products`, { headers: owner, data: { category_id: category.id, name, barcode: barcode(index), unit_price: "10.0000", currency: "USD", price_basis: "PIECE", pieces_per_box: 6, is_published: true } }));
  }
  await json(await api.put(`/api/v1/tenants/${tenantId}/storefront/slug`, { headers: owner, data: { slug } }));
  const alice = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Alice Grocer", phone: phone(7), grade: "A", address: "Alice Street 1" } }));
  const bruno = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Bruno Market", phone: phone(8), grade: "B" } }));
  const secretOf = async (customerId: unknown) => ((await json(await api.post(`/api/v1/tenants/${tenantId}/customers/${String(customerId)}/access-link`, { headers: owner, data: {} }))).storefront_path as string).split("#")[1] ?? "";
  const secretA = await secretOf(alice.id);
  const secretB = await secretOf(bruno.id);

  // One browser context = one cookie jar and one localStorage: the hard case.
  const shop = await browser.newContext({ baseURL: SHOP, locale: "en-US" });
  const tabA = await shop.newPage();
  await tabA.goto(`/${slug}/access#${secretA}`);
  await expect(tabA.getByText("Prices shown for Alice Grocer.")).toBeVisible();
  await addProduct(tabA, "Iso Water");

  const tabB = await shop.newPage();
  await tabB.goto(`/${slug}/access#${secretB}`);
  await expect(tabB.getByText("Prices shown for Bruno Market.")).toBeVisible();
  await addProduct(tabB, "Iso Rice");

  // Back to A (after B's link was opened in the same browser): still Alice, still Alice's cart.
  await tabA.reload();
  await expect(tabA.getByText("Prices shown for Alice Grocer.")).toBeVisible();
  expect(await cartLines(tabA)).toEqual([expect.stringContaining("Iso Water")]);
  await expect(tabA.getByTestId("ordering-as")).toHaveText("Ordering as Alice Grocer");
  await expect(tabA.getByLabel("Name")).toHaveCount(0);
  await expect(tabA.getByLabel("Phone")).toHaveCount(0);

  // And B: still Bruno, still Bruno's cart.
  await tabB.reload();
  await expect(tabB.getByText("Prices shown for Bruno Market.")).toBeVisible();
  expect(await cartLines(tabB)).toEqual([expect.stringContaining("Iso Rice")]);
  await expect(tabB.getByTestId("ordering-as")).toHaveText("Ordering as Bruno Market");

  // Submit both. A has a saved address (blank is allowed); B has none, so the address is required.
  await tabA.getByRole("button", { name: "Place order" }).click();
  await expect(tabA).toHaveURL(new RegExp(`/${slug}/order`));
  await expect(tabB.getByLabel("Delivery address")).toHaveAttribute("required", "");
  await tabB.getByLabel("Delivery address").fill("Bruno Road 2");
  await tabB.getByRole("button", { name: "Place order" }).click();
  await expect(tabB).toHaveURL(new RegExp(`/${slug}/order`));

  const orders = (await json(await api.get(`/api/v1/tenants/${tenantId}/orders?tenant_id=${tenantId}`, { headers: owner }))).orders as Record<string, unknown>[];
  expect(orders).toHaveLength(2);
  const byName = Object.fromEntries(orders.map((order) => [order.contact_name as string, order]));
  expect(byName["Alice Grocer"]?.linked_customer_id).toBe(alice.id);
  expect(byName["Alice Grocer"]?.contact_address).toBe("Alice Street 1");
  expect(byName["Bruno Market"]?.linked_customer_id).toBe(bruno.id);
  expect(byName["Bruno Market"]?.contact_address).toBe("Bruno Road 2");
  for (const order of orders) {
    const detail = await json(await api.get(`/api/v1/tenants/${tenantId}/orders/${String(order.id)}?tenant_id=${tenantId}`, { headers: owner }));
    const lines = ((detail.invoice as Record<string, unknown>).items as Record<string, unknown>[]).map((line) => line.product_name);
    expect(lines).toEqual([order.contact_name === "Alice Grocer" ? "Iso Water" : "Iso Rice"]);
  }

  // A link revoked while its cart page is open: the submit turns into the public checkout in place.
  await tabA.goto(`/${slug}?c=${new URL(tabA.url()).searchParams.get("c") ?? ""}`);
  await addProduct(tabA, "Iso Water");
  await tabA.getByRole("link", { name: /^Cart/ }).first().click();
  await expect(tabA.getByTestId("ordering-as")).toBeVisible();
  await json(await api.delete(`/api/v1/tenants/${tenantId}/customers/${String(alice.id)}/access-link`, { headers: owner }));
  await tabA.getByRole("button", { name: "Place order" }).click();
  await expect(tabA.getByRole("alert").filter({ hasText: "This personalized link is no longer active; enter your details to continue." })).toBeVisible();
  await tabA.getByLabel("Name").fill("Walk-in Guest");
  await tabA.getByLabel("Phone").fill(phone(20));
  await tabA.getByLabel("Delivery address").fill("Guest Lane 3");
  await tabA.getByRole("button", { name: "Place order" }).click();
  await expect(tabA).toHaveURL(new RegExp(`/${slug}/order`));
  const after = (await json(await api.get(`/api/v1/tenants/${tenantId}/orders?tenant_id=${tenantId}`, { headers: owner }))).orders as Record<string, unknown>[];
  const guestOrder = after.find((order) => order.contact_name === "Walk-in Guest");
  expect(guestOrder?.linked_customer_id).toBeNull(); // the public path, exactly as before
  expect(guestOrder?.intended_customer_id).toBeNull();
  await shop.close();
  await api.dispose();
});
