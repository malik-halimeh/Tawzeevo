import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import type { AnomaliesResponse, CashFlowResponse, InactivityResponse, PrioritiesResponse, PriorityItem } from "../api/intelligence";
import i18n from "../i18n";
import { AnomalySection, AttentionList, CashFlowSection, CustomerSignals, TodayBrief } from "./IntelligencePanel";

afterEach(async () => { cleanup(); vi.unstubAllGlobals(); await i18n.changeLanguage("en"); });

const TENANT = "t1";
const AS_OF = "2026-09-25T09:00:00Z";

function priority(overrides: Partial<PriorityItem>): PriorityItem {
  return {
    customer_id: "c-0", customer_name: "Customer", customer_grade: null, currency: "USD", score: 10, band: "LOW",
    components: { collection_urgency: 0, relationship_inactivity: 0, activity_decline: null, friction_signals: 0 },
    reasons: [], suggested_action_code: "ROUTINE_CHECK_IN", inactivity_status: "NORMAL", outstanding_balance: "0.0000", days_since_last_purchase: 3,
    ...overrides,
  };
}

const PRIORITIES: PrioritiesResponse = {
  as_of: AS_OF,
  groups: [
    { currency: "LBP", items: [priority({ customer_id: "c-lbp", customer_name: "Hamra Café", currency: "LBP", score: 40, band: "MEDIUM", suggested_action_code: "FOLLOW_UP_BALANCE", reasons: [{ code: "OUTSTANDING_BALANCE", value: "900000.0000", context: { oldest_unpaid_age_days: 12 } }] })] },
    { currency: "USD", items: [
      priority({ customer_id: "c-tyre", customer_name: "Tyre Fresh Foods", score: 88, band: "HIGH", suggested_action_code: "COLLECT_OVERDUE", reasons: [{ code: "OLD_OVERDUE_BALANCE", value: "640.5000", context: { overdue_age_days: 75, threshold_days: 30 } }, { code: "RECENT_CANCELLATIONS", value: 2, context: {} }] }),
      priority({ customer_id: "c-byblos", customer_name: "Byblos Grocery", score: 55, band: "HIGH", suggested_action_code: "REACTIVATE_CUSTOMER", inactivity_status: "LAPSED", reasons: [{ code: "PAST_NORMAL_PURCHASE_INTERVAL", value: "5.0", context: { days_since_last_purchase: 50, median_purchase_interval_days: "10", status: "LAPSED" } }] }),
      priority({ customer_id: "c-batroun", customer_name: "Batroun Bakery", score: 30, band: "MEDIUM", suggested_action_code: "CHECK_ACTIVITY_DECLINE", reasons: [{ code: "ACTIVITY_DOWN_VS_90D", value: "0.1", context: { sales_30d: "20.0000", sales_90d: "600.0000" } }] }),
      priority({ customer_id: "c-mount", customer_name: "Mount Lebanon Market", score: 5, band: "LOW" }),
    ] },
  ],
};

const INACTIVITY: InactivityResponse = {
  as_of: AS_OF,
  groups: [{ currency: "USD", items: [
    { customer_id: "c-byblos", customer_name: "Byblos Grocery", customer_grade: "B", currency: "USD", status: "LAPSED", recency_ratio: "5.0", days_since_last_purchase: 50, median_purchase_interval_days: "10", purchase_interval_mad_days: "1", invoice_count_lifetime: 14, invoice_count_90d: 4, sales_30d: "0.0000", sales_90d: "220.0000", outstanding_balance: "0.0000", last_purchase_at: "2026-08-06T09:00:00Z", reason_codes: ["PAST_NORMAL_PURCHASE_INTERVAL"] },
    { customer_id: "c-mount", customer_name: "Mount Lebanon Market", customer_grade: "A", currency: "USD", status: "NORMAL", recency_ratio: "0.4", days_since_last_purchase: 3, median_purchase_interval_days: "7", purchase_interval_mad_days: "1", invoice_count_lifetime: 26, invoice_count_90d: 13, sales_30d: "400.0000", sales_90d: "1200.0000", outstanding_balance: "0.0000", last_purchase_at: "2026-09-22T09:00:00Z", reason_codes: [] },
    { customer_id: "c-saida", customer_name: "Saida Corner Shop", customer_grade: null, currency: "USD", status: "INSUFFICIENT_HISTORY", recency_ratio: null, days_since_last_purchase: 20, median_purchase_interval_days: null, purchase_interval_mad_days: null, invoice_count_lifetime: 2, invoice_count_90d: 2, sales_30d: "0.0000", sales_90d: "80.0000", outstanding_balance: "0.0000", last_purchase_at: "2026-09-05T09:00:00Z", reason_codes: ["INSUFFICIENT_PURCHASE_HISTORY"] },
  ] }],
};

const ANOMALIES: AnomaliesResponse = {
  as_of: AS_OF,
  window: { start: "2026-09-18T21:00:00Z", end: AS_OF, timezone: "Asia/Beirut", block_days: 7, baseline_blocks: 8 },
  groups: [
    { currency: "USD", insufficient_history: ["REFUND_SPIKE"], items: [
      { type: "SALES_PERIOD_HIGH", severity: "HIGH", detected_at: AS_OF, subject_type: "TENANT", subject_id: null, metric: "confirmed_sales_7d", observed_value: "4200.0000", baseline: { method: "MEDIAN_MAD", median: "1500.0000", mad: "100.0000", sample_size: 8 }, reason_code: "ABOVE_BASELINE", details: { robust_z: "12.1" } },
      { type: "CUSTOMER_INVOICE_VALUE_HIGH", severity: "WATCH", detected_at: AS_OF, subject_type: "INVOICE", subject_id: "inv-9", metric: "invoice_net_sales", observed_value: "900.0000", baseline: { method: "MEDIAN_MAD", median: "80.0000", mad: "10.0000", sample_size: 10 }, reason_code: "ABOVE_CUSTOMER_HISTORY", details: { customer_id: "c-trip", customer_name: "Tripoli Traders", robust_z: "4.0" } },
      { type: "OVERDUE_THRESHOLD_CROSSED", severity: "WATCH", detected_at: AS_OF, subject_type: "CUSTOMER", subject_id: "c-zahle", metric: "outstanding_balance", observed_value: "310.0000", baseline: { method: "DIRECT_RULE", median: null, mad: null, sample_size: null }, reason_code: "THRESHOLD_CROSSED_RECENTLY", details: { customer_name: "Zahle Wholesale", overdue_age_days: 33, threshold_days: 30, days_past_threshold: 3 } },
      { type: "CANCELLATION_SPIKE", severity: "WATCH", detected_at: AS_OF, subject_type: "TENANT", subject_id: null, metric: "cancelled_invoices_7d", observed_value: "4", baseline: { method: "MEDIAN_MAD", median: "0", mad: "0", sample_size: 8 }, reason_code: "ABOVE_BASELINE", details: { robust_z: "4" } },
    ] },
    { currency: "LBP", insufficient_history: ["SALES_PERIOD", "SUPPLIER_PAYABLE_JUMP"], items: [] },
  ],
};

const CASH: CashFlowResponse = {
  as_of: AS_OF,
  period: { key: "90d", start: "2026-06-27T00:00:00Z", end: AS_OF, timezone: "Asia/Beirut" },
  overdue_threshold_days: 30,
  currencies: [
    {
      currency: "USD",
      position: { customer_receivables: "1450.0000", customer_credit: "0.0000", overdue_receivables: "950.5000", overdue_customer_count: 2, supplier_payables: "2000.0000", supplier_credit: "0.0000" },
      ageing: [{ bucket: "AGE_91_PLUS", amount: "100.0000", customer_count: 1 }, { bucket: "AGE_0_30", amount: "500.0000", customer_count: 3 }, { bucket: "AGE_61_90", amount: "850.0000", customer_count: 1 }],
      historical_flow: { customer_receipts: "5200.0000", customer_refunds: "150.0000", supplier_payments: "3000.0000", net_customer_collections: "5050.0000", average_weekly_collections: "388.4615" },
      planned_collections: { amount: "420.0000", task_count: 3, from_date: "2026-09-25", through_date: "2026-10-01", source: "DELIVERY_TASK_AMOUNT_TO_COLLECT", projection_warning_code: "DELIVERY_PROJECTION_IGNORES_ADJUSTMENTS" },
    },
    {
      currency: "LBP",
      position: { customer_receivables: "0.0000", customer_credit: "0.0000", overdue_receivables: "0.0000", overdue_customer_count: 0, supplier_payables: "0.0000", supplier_credit: "0.0000" },
      ageing: [],
      historical_flow: { customer_receipts: "900000.0000", customer_refunds: "0.0000", supplier_payments: "0.0000", net_customer_collections: "900000.0000", average_weekly_collections: null },
      planned_collections: { amount: "0.0000", task_count: 0, from_date: "2026-09-25", through_date: "2026-10-01", source: "DELIVERY_TASK_AMOUNT_TO_COLLECT", projection_warning_code: "DELIVERY_PROJECTION_IGNORES_ADJUSTMENTS" },
    },
  ],
};

type Route = (url: URL) => Response | Promise<Response> | undefined;
function stubApi(route: Route) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://api.test");
    calls.push(`${url.pathname}${url.search}`);
    return (await route(url)) ?? Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 });
  }));
  return calls;
}

const standard: Route = (url) => {
  if (url.pathname.endsWith("/intelligence/priorities")) return Response.json(PRIORITIES);
  if (url.pathname.endsWith("/intelligence/inactivity")) return Response.json(INACTIVITY);
  if (url.pathname.endsWith("/intelligence/anomalies")) return Response.json(ANOMALIES);
  if (url.pathname.endsWith("/intelligence/cash-flow")) return Response.json(CASH);
  return undefined;
};

function renderWith(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>);
}

// Text is matched without the left-to-right isolates that keep amounts in order inside Arabic copy.
const plain = (node: Element | null) => (node?.textContent ?? "").replace(/[⁦-⁩]/g, "");

test("Work shows the three most pressing customers across currencies, with the action, a reason and a way to open each", async () => {
  const calls = stubApi(standard);
  renderWith(<TodayBrief tenantId={TENANT} />);
  expect(screen.getByText("Working out today's picture…")).toHaveAttribute("aria-busy", "true");
  const list = await screen.findByRole("list", { name: "Today's priorities" });
  const rows = within(list).getAllByRole("link");
  expect(rows.map((row) => row.querySelector("strong")?.textContent)).toEqual(["Tyre Fresh Foods", "Byblos Grocery", "Hamra Café"]);
  expect(plain(rows[0]!)).toContain("Collect the overdue balance");
  expect(plain(rows[0]!)).toContain("640.5000 USD overdue for 75 days — well past the 30-day limit");
  expect(plain(rows[2]!)).toContain("Owes 900000.0000 LBP (oldest unpaid charge: 12 days)"); // each amount keeps its own currency
  expect(rows[0]).toHaveAttribute("href", "/workspace?tenant=t1&section=customers&customer=c-tyre");
  expect(screen.getByText("1 more customer is on the priority list in Customers.")).toBeInTheDocument();
  expect(screen.getByText(/4 unusual changes this week\./)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Review in Analytics" })).toHaveAttribute("href", "/workspace?tenant=t1&section=analytics");
  expect(calls.every((call) => call.includes("tenant_id=t1"))).toBe(true);
});

test("Work says plainly when nobody needs attention, and a failed load stays quiet with a retry", async () => {
  let fail = true;
  stubApi((url) => {
    if (url.pathname.endsWith("/priorities")) return fail ? Response.json({ detail: { code: "INTERNAL", message: "boom" } }, { status: 500 }) : Response.json({ as_of: AS_OF, groups: [{ currency: "USD", items: [priority({})] }] });
    if (url.pathname.endsWith("/anomalies")) return Response.json({ ...ANOMALIES, groups: [] });
    return undefined;
  });
  renderWith(<TodayBrief tenantId={TENANT} />);
  expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent("boom"); // after the one automatic retry
  fail = false;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("No customer needs special attention today.")).toBeInTheDocument();
  expect(screen.queryByText(/unusual change/)).not.toBeInTheDocument();
});

test("Customers ranks attention per currency, hides low priority until asked, and switches to buying rhythm", async () => {
  const calls = stubApi(standard);
  renderWith(<AttentionList tenantId={TENANT} />);
  const usd = await screen.findByRole("list", { name: "Priorities · USD" });
  expect(within(usd).getAllByRole("link").map((row) => row.querySelector("strong")?.textContent)).toEqual(["Tyre Fresh Foods", "Byblos Grocery", "Batroun Bakery"]);
  expect(within(usd).getAllByText(/High priority/)[0]).toHaveTextContent("High priority · 88");
  expect(plain(usd)).toContain("Buying less: 20.0000 USD in the last 30 days against 600.0000 USD over 90 days");
  expect(plain(usd)).toContain("2 recent cancellations");
  expect(screen.getByRole("heading", { name: "LBP" })).toBeInTheDocument();
  expect(screen.getByText(/Currencies are listed separately on purpose/)).toBeInTheDocument();
  expect(screen.getByText(/The score orders the list; it is not a probability\./)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show all 5 customers" }));
  expect(within(screen.getByRole("list", { name: "Priorities · USD" })).getByText("Mount Lebanon Market")).toBeInTheDocument();

  expect(calls.some((call) => call.includes("/inactivity"))).toBe(false); // loaded only when asked for
  fireEvent.click(screen.getByRole("button", { name: "Buying rhythm" }));
  expect(screen.getByRole("button", { name: "Buying rhythm" })).toHaveAttribute("aria-pressed", "true");
  const rhythm = await screen.findByRole("list", { name: "Buying rhythm · USD" });
  expect(within(rhythm).getAllByRole("link").map((row) => row.querySelector("strong")?.textContent)).toEqual(["Byblos Grocery"]);
  expect(plain(rhythm)).toContain("Last purchase 50 days ago; usually buys every 10 days.");
  expect(within(rhythm).getByText("Stopped buying")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show all 3 customers" }));
  expect(plain(screen.getByRole("list", { name: "Buying rhythm · USD" }))).toContain("Only 2 confirmed invoices — too few to know their buying rhythm.");
});

test("Customers with no history yet get an explanation instead of an empty list", async () => {
  stubApi((url) => (url.pathname.endsWith("/priorities") ? Response.json({ as_of: AS_OF, groups: [] }) : undefined));
  renderWith(<AttentionList tenantId={TENANT} />);
  expect(await screen.findByText(/Nothing to rank yet/)).toBeInTheDocument();
});

test("a customer's record explains its signals per currency, or says there are none", async () => {
  stubApi(standard);
  const { unmount } = renderWith(<CustomerSignals customerId="c-byblos" tenantId={TENANT} />);
  const signals = await screen.findByRole("region", { name: "Signals" });
  await waitFor(() => expect(plain(signals)).toContain("Check in — they have stopped buying"));
  expect(within(signals).getByText("Stopped buying")).toBeInTheDocument();
  expect(plain(signals)).toContain("No purchase for 50 days; usually buys every 10 days");
  expect(plain(signals)).toContain("It is not a probability.");
  unmount();
  renderWith(<CustomerSignals customerId="c-unknown" tenantId={TENANT} />);
  expect(await screen.findByText(/No signals yet/)).toBeInTheDocument();
});

test("the cash position shows overdue, ageing in order, net collections and a labelled delivery projection — never a forecast", async () => {
  const calls = stubApi(standard);
  renderWith(<CashFlowSection period="90d" tenantId={TENANT} />);
  const usd = await screen.findByRole("article", { name: "Cash position in USD" });
  expect(plain(usd)).toContain("950.5000 USD of 1450.0000 USD owed (2 customers)");
  expect(plain(usd)).toContain("5050.0000 USD · refunds paid 150.0000 USD");
  const ageing = within(usd).getByRole("table", { name: "Unpaid balances by age, USD" });
  expect(within(ageing).getAllByRole("row").slice(1).map((row) => row.firstChild?.textContent)).toEqual(["0–30 days", "61–90 days", "Over 90 days"]);
  expect(plain(usd)).toContain("Planned deliveries from 2026-09-25 to 2026-10-01: 420.0000 USD to collect on 3 deliveries.");
  expect(plain(usd)).toContain("it leaves out later invoice adjustments and is not a promise of payment");
  const lbp = screen.getByRole("article", { name: "Cash position in LBP" });
  expect(plain(lbp)).toContain("No customer owes anything in this currency.");
  expect(plain(lbp)).not.toContain("USD");
  expect(document.body.textContent).not.toMatch(/probabilit|will pay|expected payment|runway/i);
  expect(calls).toEqual(["/api/v1/intelligence/cash-flow?tenant_id=t1&period=90d"]);
});

test("unusual changes read as prompts to look, link to their record and say which checks lack history", async () => {
  stubApi(standard);
  renderWith(<AnomalySection tenantId={TENANT} />);
  const usd = await screen.findByRole("list", { name: "Unusual changes in USD" });
  const items = within(usd).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Sales this week are unusually high");
  expect(within(items[0]!).getByText("Very unusual")).toBeInTheDocument();
  expect(plain(items[0]!)).toContain("4200.0000 USD this week; usually about 1500.0000 USD a week");
  expect(plain(items[1]!)).toContain("Tripoli Traders: an invoice of 900.0000 USD; this customer's invoices are usually about 80.0000 USD");
  expect(within(items[1]!).getByRole("link", { name: "Open the invoice" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=inv-9");
  expect(within(items[2]!).getByRole("link", { name: "Open the customer" })).toHaveAttribute("href", "/workspace?tenant=t1&section=customers&customer=c-zahle");
  expect(plain(items[3]!)).toContain("4 this week; usually about 0 a week"); // a count, not an amount
  expect(plain(items[3]!)).not.toContain("4 USD");
  expect(screen.getByText("Not enough history yet in USD to check: refunds.")).toBeInTheDocument();
  expect(screen.getByText("Not enough history yet in LBP to check: weekly sales, supplier balances.")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/fraud|suspicious/i);
});

test("a quiet week is said in words", async () => {
  stubApi((url) => (url.pathname.endsWith("/anomalies") ? Response.json({ ...ANOMALIES, groups: [{ currency: "USD", items: [], insufficient_history: [] }] }) : undefined));
  renderWith(<AnomalySection tenantId={TENANT} />);
  expect(await screen.findByText("Nothing unusual in the last 7 days.")).toBeInTheDocument();
});

test("Arabic owners get the same ranking in Arabic, with amounts kept left-to-right", async () => {
  await i18n.changeLanguage("ar");
  stubApi(standard);
  renderWith(<AttentionList tenantId={TENANT} />);
  const usd = await screen.findByRole("list", { name: "الأولويات · USD" });
  expect(within(usd).getAllByText(/أولوية عالية/)[0]).toHaveTextContent("أولوية عالية · 88");
  expect(within(usd).getAllByText("حصّل الرصيد المتأخر")).toHaveLength(1);
  const reason = within(usd).getByText(/متأخر منذ/);
  expect(reason.textContent).toContain("⁦640.5000 USD⁩"); // isolated so the currency stays after the amount
  expect(within(usd).getByText("إلغاءان حديثان")).toBeInTheDocument(); // Arabic dual form
  expect(screen.getByRole("button", { name: "إيقاع الشراء" })).toBeInTheDocument();
});
