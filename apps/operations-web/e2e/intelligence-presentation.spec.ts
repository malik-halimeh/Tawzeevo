import { expect, request as playwrightRequest, test } from "@playwright/test";

/**
 * Owner intelligence in real browsers (D-089): a customer with an old overdue balance appears in
 * today's priorities on Work, opens as a record with its reasons, the Analytics cash position shows
 * the same overdue amount in its age bucket, and the business assistant either explains that it is
 * not switched on (the real API here has no provider key) or — with the provider answers stubbed in
 * the browser, never a paid call — answers with sources and a customer link that opens the record.
 * A phone-width Work screen stays within the viewport.
 *
 * Environment: E2E_API_URL, E2E_WEB_URL, E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD. The API must run
 * without GROQ_API_KEY.
 */
const API = process.env.E2E_API_URL ?? "http://127.0.0.1:8011";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin-e2e@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2eAdminPassword123!";
const PASSWORD = "E2eOwnerPassword123!";
const stamp = Date.now().toString(36);
const ownerEmail = `owner-intel-${stamp}@example.com`;
// Amounts are wrapped in left-to-right isolates (so Arabic copy never reorders them); match through them.
const loose = (text: string) => new RegExp([...text].map((char) => char.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("[\\u2066-\\u2069]*"));

test("priorities, a customer's signals, cash ageing and the assistant work together for the owner", async ({ page }) => {
  test.setTimeout(180_000);
  const api = await playwrightRequest.newContext({ baseURL: API });
  const json = async (response: Awaited<ReturnType<typeof api.post>>) => {
    expect(response.ok(), `${response.url()} -> ${response.status()} ${await response.text()}`).toBeTruthy();
    return (await response.json()) as Record<string, unknown>;
  };
  const phone = (n: number) => `+96176${((Date.now() + n) % 1_000_000).toString().padStart(6, "0")}`;

  // ----- Setup: owner, business, a 7-day overdue limit and a customer owing 250 USD for 40 days -----
  await json(await api.post("/register", { data: { first_name: "Rana", last_name: "Intel", email: ownerEmail, phone: phone(1), city: "Beirut", age: 36, password: PASSWORD } }));
  const ownerToken = (await json(await api.post("/login", { data: { email: ownerEmail, password: PASSWORD } }))).access_token as string;
  const adminToken = (await json(await api.post("/login", { data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD } }))).access_token as string;
  const owner = { Authorization: `Bearer ${ownerToken}` };
  const application = await json(await api.post("/api/v1/tenant-applications", { headers: owner, data: { business_name: `Intel Van ${stamp}` } }));
  const approved = await json(await api.post(`/api/v1/platform/tenant-applications/${String(application.id)}/approve`, { headers: { Authorization: `Bearer ${adminToken}` }, data: {} }));
  const tenantId = (approved.tenant_id ?? (approved.tenant as Record<string, unknown> | undefined)?.id) as string;
  await json(await api.put(`/api/v1/customer-ledger/settings?tenant_id=${tenantId}`, { headers: owner, data: { customer_overdue_threshold_days: 7 } }));
  const overdue = await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Tyre Fresh Foods", phone: phone(3), grade: "B", address: "Tyre souk" } }));
  await json(await api.post(`/api/v1/tenants/${tenantId}/customers`, { headers: owner, data: { name: "Mount Lebanon Market", phone: phone(4), grade: "A" } }));
  await json(await api.post(`/api/v1/customer-ledger/opening-balances?tenant_id=${tenantId}`, { headers: owner, data: { idempotency_key: crypto.randomUUID(), customer_id: overdue.id, currency: "USD", signed_amount: "250.0000", effective_at: new Date(Date.now() - 40 * 86_400_000).toISOString() } }));

  // The API computes the facts the screens will show; the browser must show exactly these.
  const priorities = await json(await api.get(`/api/v1/intelligence/priorities?tenant_id=${tenantId}`, { headers: owner }));
  const top = (priorities.groups as { currency: string; items: { customer_id: string; band: string; suggested_action_code: string }[] }[])[0];
  expect(top.currency).toBe("USD");
  expect(top.items[0]).toMatchObject({ customer_id: overdue.id, band: "HIGH", suggested_action_code: "COLLECT_OVERDUE" });

  // ----- Work: today's priorities, above the day's stops -----
  await page.goto("/login");
  await page.getByLabel("Email").fill(ownerEmail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/workspace/);
  const today = page.getByRole("list", { name: "Today's priorities" });
  await expect(today.getByRole("link")).toHaveCount(1);
  await expect(today).toContainText("Tyre Fresh Foods");
  await expect(today).toContainText("Collect the overdue balance");
  await expect(today).toContainText(loose("250.0000 USD overdue for 40 days"));

  // ----- The priority opens the customer's record with the phone to call and the reasons -----
  await today.getByRole("link", { name: /Tyre Fresh Foods/ }).click();
  await expect(page).toHaveURL(new RegExp(`section=customers.*customer=${String(overdue.id)}`));
  const record = page.getByRole("article", { name: "Tyre Fresh Foods" });
  await expect(record).toContainText(overdue.phone as string);
  const signals = record.getByRole("region", { name: "Signals" });
  await expect(signals).toContainText("High priority");
  await expect(signals).toContainText("It is not a probability.");
  await expect(page.getByRole("list", { name: "Priorities · USD" })).toContainText("Tyre Fresh Foods");

  // ----- Analytics: the same 250 USD is overdue and sits in the 31–60 day bucket -----
  const rail = page.getByRole("navigation", { name: "Workspace navigation" });
  await rail.getByRole("link", { name: "Analytics", exact: true }).click();
  const cash = page.getByRole("article", { name: "Cash position in USD" });
  await expect(cash).toContainText(loose("250.0000 USD of 250.0000 USD owed (1 customer)"));
  await expect(cash.getByRole("table", { name: "Unpaid balances by age, USD" })).toContainText("31–60 days");
  await expect(page.getByRole("heading", { name: "Unusual changes this week" })).toBeVisible();
  await expect(page.getByText(/Nothing unusual in the last 7 days\.|Not enough history yet/).first()).toBeVisible();
  await expect(page.locator(".intel-cash")).not.toContainText(/probabilit|will pay/i);

  // ----- Assistant without a provider key: a clear setup state, nothing else affected -----
  await rail.getByRole("link", { name: "Assistant", exact: true }).click();
  await expect(page.getByText("The assistant is not switched on")).toBeVisible();
  await page.getByRole("link", { name: "See today's priorities" }).click();
  await expect(page.getByRole("list", { name: "Priorities · USD" })).toContainText("Tyre Fresh Foods");

  // ----- Assistant with the provider stubbed in the browser (no paid call): sources and a customer link -----
  let asked: unknown;
  await page.route("**/api/v1/intelligence/copilot/status**", (route) => route.fulfill({ json: { configured: true, provider: "groq", model: "stub" } }));
  await page.route("**/api/v1/intelligence/copilot/query**", async (route) => {
    asked = route.request().postDataJSON();
    await route.fulfill({ json: {
      conversation_id: "2b7f0b5e-5d0e-4a5b-9a2a-0f6f7a1d2c3e",
      answer: "Call Tyre Fresh Foods first: 250.0000 USD has been overdue for 40 days.",
      conversation_text: "Call C-TYRE01 first: 250.0000 USD has been overdue for 40 days.",
      references: [{ ref: "C-TYRE01", customer_id: overdue.id, customer_name: "Tyre Fresh Foods" }],
      grounding: [{ tool: "get_daily_priorities", period: null, currency: "USD", ok: true }],
      warnings: [], unverified_numbers: [],
    } });
  });
  await page.goto(`/workspace?tenant=${tenantId}&section=assistant`);
  await page.getByRole("button", { name: "Who should I call today?" }).click();
  const conversation = page.getByRole("list", { name: "Conversation" });
  await expect(conversation).toContainText("Call Tyre Fresh Foods first: 250.0000 USD has been overdue for 40 days.");
  await expect(conversation).toContainText("Today's priorities · USD");
  expect(asked).toEqual({ message: "Who should I call today?", conversation: [] });
  await conversation.getByRole("link", { name: "Tyre Fresh Foods" }).click();
  await expect(page.getByRole("article", { name: "Tyre Fresh Foods" })).toBeVisible();

  // ----- Phone width: Work keeps the priorities inside the screen -----
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/workspace?tenant=${tenantId}`);
  await expect(page.getByRole("list", { name: "Today's priorities" })).toBeVisible();
  const overflow = await page.evaluate<number>("document.documentElement.scrollWidth - window.innerWidth");
  expect(overflow).toBeLessThanOrEqual(0);
});
