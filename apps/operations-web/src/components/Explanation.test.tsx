import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { AnomalySection, CashFlowSection, CustomerSignals } from "./IntelligencePanel";

afterEach(async () => { cleanup(); vi.unstubAllGlobals(); await i18n.changeLanguage("en"); });

const TENANT = "t1";
const AS_OF = "2026-09-25T09:00:00Z";
const PRIORITIES = { as_of: AS_OF, groups: [{ currency: "USD", items: [
  { customer_id: "c-tyre", customer_name: "Tyre Fresh Foods", customer_grade: "B", currency: "USD", score: 88, band: "HIGH", components: { collection_urgency: 40, relationship_inactivity: 0, activity_decline: null, friction_signals: 0 }, reasons: [{ code: "OLD_OVERDUE_BALANCE", value: "640.5000", context: { overdue_age_days: 75, threshold_days: 30 } }], suggested_action_code: "COLLECT_OVERDUE", inactivity_status: "NORMAL", outstanding_balance: "640.5000", days_since_last_purchase: 6 },
  { customer_id: "c-byblos", customer_name: "Byblos Grocery", customer_grade: "B", currency: "USD", score: 50, band: "HIGH", components: { collection_urgency: 0, relationship_inactivity: 30, activity_decline: 20, friction_signals: 0 }, reasons: [], suggested_action_code: "REACTIVATE_CUSTOMER", inactivity_status: "LAPSED", outstanding_balance: "0.0000", days_since_last_purchase: 50 },
] }] };
const ANOMALIES = { as_of: AS_OF, window: { start: AS_OF, end: AS_OF, timezone: "Asia/Beirut", block_days: 7, baseline_blocks: 8 }, groups: [{ currency: "USD", insufficient_history: [], items: [
  { type: "SALES_PERIOD_HIGH", severity: "HIGH", detected_at: AS_OF, subject_type: "TENANT", subject_id: null, metric: "confirmed_sales_7d", observed_value: "4200.0000", baseline: { method: "MEDIAN_MAD", median: "1500.0000", mad: "100.0000", sample_size: 8 }, reason_code: "ABOVE_BASELINE", details: {} },
  { type: "CUSTOMER_INVOICE_VALUE_HIGH", severity: "WATCH", detected_at: AS_OF, subject_type: "INVOICE", subject_id: "inv-9", metric: "invoice_net_sales", observed_value: "900.0000", baseline: { method: "MEDIAN_MAD", median: "80.0000", mad: "10.0000", sample_size: 10 }, reason_code: "ABOVE_CUSTOMER_HISTORY", details: { customer_id: "c-trip", customer_name: "Tripoli Traders" } },
] }] };
const CASH = { as_of: AS_OF, period: { key: "90d", start: null, end: AS_OF, timezone: "Asia/Beirut" }, overdue_threshold_days: 30, currencies: [
  { currency: "USD", position: { customer_receivables: "1450.0000", customer_credit: "0.0000", overdue_receivables: "950.5000", overdue_customer_count: 2, supplier_payables: "0.0000", supplier_credit: "0.0000" }, ageing: [{ bucket: "AGE_0_30", amount: "500.0000", customer_count: 3 }], historical_flow: { customer_receipts: "5200.0000", customer_refunds: "0.0000", supplier_payments: "0.0000", net_customer_collections: "5200.0000", average_weekly_collections: "400.0000" }, planned_collections: { amount: "420.0000", task_count: 3, from_date: "2026-09-25", through_date: "2026-10-01", source: "DELIVERY_TASK_AMOUNT_TO_COLLECT", projection_warning_code: "DELIVERY_PROJECTION_IGNORES_ADJUSTMENTS" } },
] };

function explanation(kind: string, answer: string, extra: Record<string, unknown> = {}) {
  return { kind, as_of: "2026-09-25T11:05:00Z", answer, references: [], grounding: [], warnings: [], unverified_numbers: [], ...extra };
}

/** The intelligence API with a configurable assistant; explanation answers are queued per test. */
function stubApi({ configured = true, answers = [] as (Response | (() => Response))[] } = {}) {
  const asked: Record<string, unknown>[] = [];
  const gets: string[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : input.toString(), "http://api.test");
    if (url.pathname.endsWith("/intelligence/explain") && init?.method === "POST") {
      asked.push(JSON.parse(init.body as string) as Record<string, unknown>);
      const next = answers.shift();
      return Promise.resolve(typeof next === "function" ? next() : next ?? Response.json(explanation("x", "ok")));
    }
    gets.push(url.pathname);
    if (url.pathname.endsWith("/copilot/status")) return Promise.resolve(Response.json(configured ? { configured: true, provider: "groq", model: "m" } : { configured: false, provider: null, model: null }));
    if (url.pathname.endsWith("/priorities")) return Promise.resolve(Response.json(PRIORITIES));
    if (url.pathname.endsWith("/inactivity")) return Promise.resolve(Response.json({ as_of: AS_OF, groups: [] }));
    if (url.pathname.endsWith("/anomalies")) return Promise.resolve(Response.json(ANOMALIES));
    if (url.pathname.endsWith("/cash-flow")) return Promise.resolve(Response.json(CASH));
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url.pathname } }, { status: 404 }));
  }));
  return { asked, gets };
}

function renderWith(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrap = (child: ReactNode) => <QueryClientProvider client={client}><MemoryRouter>{child}</MemoryRouter></QueryClientProvider>;
  const view = render(wrap(node));
  return { ...view, rerender: (next: ReactNode) => view.rerender(wrap(next)) };
}

test("a customer's record offers a brief on request, shows it with its sources and customers, and never carries it to another customer", async () => {
  const { asked } = stubApi({ answers: [Response.json(explanation("customer", "Tyre Fresh Foods owes 640.5000 USD, overdue for 75 days.\n- Ask when they can settle it.", {
    references: [{ ref: "C-AAAAAA", customer_id: "c-tyre", customer_name: "Tyre Fresh Foods" }],
    grounding: [{ tool: "get_daily_priorities", period: null, currency: null, ok: true }, { tool: "get_customer_debts", period: null, currency: null, ok: true }],
  }))] });
  const view = renderWith(<CustomerSignals customerId="c-tyre" tenantId={TENANT} />);
  const signals = await screen.findByRole("region", { name: "Signals" });
  const ask = await within(signals).findByRole("button", { name: "Summarize this customer" });
  expect(asked).toEqual([]); // nothing is sent until the owner asks
  fireEvent.click(ask);
  expect(await within(signals).findByText("Tyre Fresh Foods owes 640.5000 USD, overdue for 75 days.")).toBeInTheDocument();
  expect(asked).toEqual([{ kind: "customer", customer_id: "c-tyre", language: "en" }]);
  expect(within(signals).getByText("Ask when they can settle it.").tagName).toBe("LI");
  expect(within(signals).getByText(/Written at .* from Tawzeevo's figures/)).toBeInTheDocument();
  expect(within(signals).getByRole("link", { name: "Tyre Fresh Foods" })).toHaveAttribute("href", "/workspace?tenant=t1&section=customers&customer=c-tyre");
  expect(signals).toHaveTextContent("Based on:Today's prioritiesCustomer balances");
  expect(within(signals).getByText("Collect the overdue balance")).toBeInTheDocument(); // the calculated signals stay

  view.rerender(<CustomerSignals customerId="c-byblos" tenantId={TENANT} />);
  expect(await screen.findByRole("button", { name: "Summarize this customer" })).toBeInTheDocument();
  expect(screen.queryByText(/Tyre Fresh Foods owes/)).not.toBeInTheDocument();
  expect(asked).toHaveLength(1);
});

test("without a switched-on assistant the record says so in one line and unusual changes offer no Explain", async () => {
  const { asked } = stubApi({ configured: false });
  renderWith(<><CustomerSignals customerId="c-tyre" tenantId={TENANT} /><AnomalySection tenantId={TENANT} /></>);
  expect(await screen.findByText("A written summary appears here once the business assistant is switched on.")).toBeInTheDocument();
  await screen.findByRole("list", { name: "Unusual changes in USD" });
  expect(screen.queryByRole("button", { name: "Explain this change" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Summarize this customer" })).not.toBeInTheDocument();
  expect(screen.getByText("Collect the overdue balance")).toBeInTheDocument(); // calculated facts unaffected
  expect(asked).toEqual([]);
});

test("an unusual change is explained in its own row, keeping its record link", async () => {
  const { asked } = stubApi({ answers: [Response.json(explanation("anomaly", "An invoice of 900.0000 USD, against a usual 80.0000 USD for this customer. Check the invoice lines."))] });
  renderWith(<AnomalySection tenantId={TENANT} />);
  const list = await screen.findByRole("list", { name: "Unusual changes in USD" });
  const rows = within(list).getAllByRole("listitem");
  expect(await within(rows[0]!).findByRole("button", { name: "Explain this change" })).toBeInTheDocument();
  fireEvent.click(within(rows[1]!).getByRole("button", { name: "Explain this change" }));
  expect(await within(rows[1]!).findByText(/An invoice of 900.0000 USD/)).toBeInTheDocument();
  expect(asked).toEqual([{ kind: "anomaly", currency: "USD", index: 1, type: "CUSTOMER_INVOICE_VALUE_HIGH", subject_id: "inv-9", language: "en" }]);
  expect(within(rows[1]!).getByRole("link", { name: "Open the invoice" })).toHaveAttribute("href", "/workspace?tenant=t1&section=invoices&invoice=inv-9");
  expect(within(rows[0]!).queryByText(/An invoice of/)).not.toBeInTheDocument();
});

test("a change that moved on is reported and the list is reloaded instead of retrying", async () => {
  const { gets } = stubApi({ answers: [Response.json({ detail: { code: "ANOMALY_CHANGED", message: "changed" } }, { status: 409 })] });
  renderWith(<AnomalySection tenantId={TENANT} />);
  const list = await screen.findByRole("list", { name: "Unusual changes in USD" });
  const before = gets.filter((path) => path.endsWith("/anomalies")).length;
  fireEvent.click((await within(list).findAllByRole("button", { name: "Explain this change" }))[0]!);
  expect(await screen.findByRole("alert")).toHaveTextContent("This unusual change is no longer current");
  await waitFor(() => expect(gets.filter((path) => path.endsWith("/anomalies")).length).toBe(before + 1));
  expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
});

test("the cash summary follows the selected period, recovers from a failure and flags figures it was not given", async () => {
  const { asked } = stubApi({ answers: [
    Response.json({ detail: { code: "COPILOT_PROVIDER_UNAVAILABLE", message: "down" } }, { status: 502 }),
    Response.json(explanation("cash", "USD: 950.5000 USD of 1450.0000 USD owed is overdue. You will collect 9999 USD.", {
      grounding: [{ tool: "get_cashflow_summary", period: "90d", currency: null, ok: true }],
      warnings: ["UNVERIFIED_NUMBERS"], unverified_numbers: ["9999"],
    })),
  ] });
  const view = renderWith(<CashFlowSection period="90d" tenantId={TENANT} />);
  fireEvent.click(await screen.findByRole("button", { name: "Summarize the cash position" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("did not answer in time");
  expect(screen.getByRole("article", { name: "Cash position in USD" })).toBeInTheDocument(); // figures stay
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText(/950.5000 USD of 1450.0000 USD owed is overdue/)).toBeInTheDocument();
  expect(screen.getByRole("note").textContent?.replace(/[⁦-⁩]/g, "")).toContain("Check these figures before relying on them: 9999.");
  expect(screen.getByText("Cash position", { exact: false, selector: ".badge" })).toHaveTextContent("Cash position · Last 90 days");
  expect(asked).toEqual([{ kind: "cash", period: "90d", language: "en" }, { kind: "cash", period: "90d", language: "en" }]);

  view.rerender(<CashFlowSection period="30d" tenantId={TENANT} />);
  expect(await screen.findByRole("button", { name: "Summarize the cash position" })).toBeInTheDocument();
  expect(screen.queryByText(/owed is overdue/)).not.toBeInTheDocument(); // no summary of another period
  expect(asked).toHaveLength(2);
});

test("in Arabic the request asks for Arabic and the summary reads right to left", async () => {
  await i18n.changeLanguage("ar");
  const { asked } = stubApi({ answers: [Response.json(explanation("customer", "على Tyre Fresh Foods مبلغ 640.5000 USD متأخر منذ 75 يوماً."))] });
  renderWith(<CustomerSignals customerId="c-tyre" tenantId={TENANT} />);
  fireEvent.click(await screen.findByRole("button", { name: "لخّص وضع هذا العميل" }));
  const text = await screen.findByText(/متأخر منذ 75 يوماً/);
  expect(text.closest("[dir]")).toHaveAttribute("dir", "rtl");
  expect(asked[0]).toMatchObject({ language: "ar" });
  expect(screen.getByRole("button", { name: "اكتب مجدداً" })).toBeInTheDocument();
});
