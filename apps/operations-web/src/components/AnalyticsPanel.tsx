import { money } from "../utils/money";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { Customer, CustomerSearchResponse } from "../api/types";
import { AnomalySection, CashFlowSection } from "./IntelligencePanel";
import { ErrorState } from "./Ui";
import { ListHeader } from "./listKit/ListHeader";

/**
 * Owner analytics baseline (PHASE_08.md A/B/C/H; D-064–D-068). Every figure is shown with its
 * currency and currencies are never added together. "Current state" and "Event flow" are two
 * named views; profit is never shown without its cost coverage. Text and numbers carry the
 * meaning — no colour-only signals.
 */
interface CurrencyAmount { currency: string; amount: string }
interface Profit { currency: string; gross_profit: string; covered_lines: number; total_lines: number; uncovered_lines: number; coverage_percent: string }
interface Overview { period: { key: string; start: string | null; end: string; timezone: string }; confirmed_invoices: number; invoiced_sales: CurrencyAmount[]; customer_receipts: CurrencyAmount[]; customer_refunds: CurrencyAmount[]; customer_outstanding: CurrencyAmount[]; customer_credit: CurrencyAmount[]; supplier_payable: CurrencyAmount[]; supplier_credit: CurrencyAmount[]; gross_profit: Profit[] }
interface Flow { totals: { currency: string; confirmations: string; edit_deltas: string; cancellations: string; net_effect: string }[]; monthly: { currency: string; month: string; net_effect: string }[] }
type PeriodKey = "30d" | "90d" | "1y" | "all";
interface CurrencyStat { currency: string; total_purchased: string; invoice_count: number; largest_invoice: string | null; average_invoice: string | null; total_receipts: string; total_refunds: string; outstanding: string; credit: string; total_discounts: string; total_markups: string }
interface TopItem { currency: string; name: string; quantity: string; value: string }
interface Lifetime { customer_id: string; customer_name: string; current_grade: string | null; financial: CurrencyStat[]; invoice_count: number; cancelled_invoices: number; cancellation_requests: number; first_purchase_at: string | null; latest_purchase_at: string | null; average_days_between_purchases: string | null; purchases_per_month: string | null; late_payment_count: number; overdue_threshold_days: number | null; monthly_spend: { currency: string; month: string; amount: string }[]; top_products: TopItem[]; top_categories: TopItem[]; grade_timeline: { at: string; grade: string | null }[]; insufficient_data: boolean }

export function AnalyticsPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<PeriodKey>("30d");
  const [overview, setOverview] = useState<Overview>();
  const [flow, setFlow] = useState<Flow>();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [phoneSearch, setPhoneSearch] = useState("");
  // "No customer" is an answer to a finished search, never to a number still being typed.
  const [searched, setSearched] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [lifetime, setLifetime] = useState<Lifetime>();
  const [error, setError] = useState<unknown>();

  const load = useCallback(async () => {
    const [o, f] = await Promise.all([
      apiRequest<Overview>(`/api/v1/analytics/overview?tenant_id=${tenantId}&period=${period}`),
      apiRequest<Flow>(`/api/v1/analytics/events?tenant_id=${tenantId}&period=${period}`),
    ]);
    setOverview(o); setFlow(f);
  }, [tenantId, period]);
  useEffect(() => { load().catch(setError); }, [load]);
  // Customers are found by phone, like everywhere else on the desk (there is no list-all endpoint).
  const findCustomers = (event: FormEvent) => {
    event.preventDefault();
    setError(undefined);
    apiRequest<CustomerSearchResponse>(`/api/v1/tenants/${tenantId}/customers/search?phone=${encodeURIComponent(phoneSearch)}`)
      .then((body) => { setCustomers(body.customers); setCustomerId(body.customers.length === 1 ? body.customers[0]!.id : ""); setSearched(true); })
      .catch(setError);
  };
  useEffect(() => {
    if (!customerId) { setLifetime(undefined); return; }
    apiRequest<Lifetime>(`/api/v1/analytics/customers/${customerId}?tenant_id=${tenantId}`).then(setLifetime).catch(setError);
  }, [customerId, tenantId]);
  const when = (value: string | null) => (value ? new Date(value).toLocaleDateString() : "—");

  const moneyList = (rows: CurrencyAmount[]) => (rows.length ? rows.map((row) => money(row.amount, row.currency)).join(" · ") : "—");
  const currencies = [...new Set([...(overview?.invoiced_sales ?? []), ...(overview?.customer_outstanding ?? []), ...(overview?.supplier_payable ?? [])].map((row) => row.currency))];

  return (
    <section className="analytics-panel" aria-label={t("analytics.title")}>
      <ListHeader eyebrow={t("analytics.kicker")} title={t("analytics.title")} />
      <p>{t("analytics.body")}</p>
      {error ? <ErrorState error={error} /> : null}
      <label className="field"><span>{t("analytics.period")}</span>
        <select value={period} onChange={(event) => setPeriod(event.target.value as PeriodKey)}>
          <option value="30d">{t("analytics.periods.30d")}</option>
          <option value="90d">{t("analytics.periods.90d")}</option>
          <option value="1y">{t("analytics.periods.1y")}</option>
          <option value="all">{t("analytics.periods.all")}</option>
        </select>
      </label>
      {overview ? (
        <>
          <p className="muted">{t("analytics.window", { count: overview.confirmed_invoices, timezone: overview.period.timezone })}</p>
          <h4>{t("analytics.currentState")}</h4>
          <dl className="sync-facts analytics-facts">
            <div><dt>{t("analytics.invoicedSales")}</dt><dd dir="ltr"><bdi dir="ltr">{moneyList(overview.invoiced_sales)}</bdi></dd></div>
            <div><dt>{t("analytics.receipts")}</dt><dd dir="ltr"><bdi dir="ltr">{moneyList(overview.customer_receipts)}</bdi></dd></div>
            <div><dt>{t("analytics.refunds")}</dt><dd dir="ltr"><bdi dir="ltr">{moneyList(overview.customer_refunds)}</bdi></dd></div>
            <div><dt>{t("analytics.customerOutstanding")}</dt><dd dir="ltr"><bdi dir="ltr">{moneyList(overview.customer_outstanding)}{overview.customer_credit.length ? ` (${t("purchases.credit")} ${moneyList(overview.customer_credit)})` : ""}</bdi></dd></div>
            <div><dt>{t("analytics.supplierPayable")}</dt><dd dir="ltr"><bdi dir="ltr">{moneyList(overview.supplier_payable)}{overview.supplier_credit.length ? ` (${t("purchases.credit")} ${moneyList(overview.supplier_credit)})` : ""}</bdi></dd></div>
          </dl>
          {/* D-089: how old what customers owe is, what came in, and what this week did differently. */}
          <CashFlowSection period={period} tenantId={tenantId} />
          <AnomalySection tenantId={tenantId} />
          <h4>{t("analytics.profitTitle")}</h4>
          <p className="muted">{t("analytics.profitBody")}</p>
          {overview.gross_profit.length === 0 ? <p className="muted">—</p> : (
            // Real tables: on a narrow screen each scrolls inside its own region instead of widening the page.
            <div aria-label={t("analytics.profitTitle")} className="table-region" role="region" tabIndex={0}>
              <table className="order-lines" aria-label={t("analytics.profitTitle")}>
                <thead><tr><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.grossProfit")}</th><th>{t("analytics.coverage")}</th><th>{t("analytics.uncovered")}</th></tr></thead>
                <tbody>{overview.gross_profit.map((row) => <tr key={row.currency}><td>{row.currency}</td><td dir="ltr"><bdi dir="ltr">{money(row.gross_profit, row.currency)}</bdi></td><td dir="ltr">{row.coverage_percent}% ({row.covered_lines}/{row.total_lines})</td><td dir="ltr">{row.uncovered_lines > 0 ? t("analytics.uncoveredLines", { count: row.uncovered_lines }) : t("analytics.allCovered")}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          {currencies.length > 1 ? <p className="muted">{t("analytics.noMixing")}</p> : null}
        </>
      ) : null}
      <h4>{t("analytics.lifetimeTitle")}</h4>
      <p className="muted">{t("analytics.lifetimeBody")}</p>
      <form className="inline-form" onSubmit={findCustomers}>
        <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" required value={phoneSearch} onChange={(event) => { setPhoneSearch(event.target.value); setSearched(false); }} /></label>
        <button className="button" type="submit">{t("common.search")}</button>
      </form>
      {customers.length > 1 ? (
        <label className="field"><span>{t("tenantWorkspace.customers")}</span>
          <select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
            <option value="">—</option>
            {customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name} · {customer.phone}</option>)}
          </select>
        </label>
      ) : null}
      {searched && customers.length === 0 && !lifetime ? <p className="muted">{t("analytics.noCustomer")}</p> : null}
      {lifetime ? (
        <div className="lifetime" aria-live="polite">
          {lifetime.insufficient_data ? <p className="muted">{t("analytics.insufficient")}</p> : (
            <>
              <dl className="sync-facts analytics-facts">
                <div><dt>{t("analytics.currentGrade")}</dt><dd>{lifetime.current_grade ?? "—"}</dd></div>
                <div><dt>{t("analytics.invoices")}</dt><dd dir="ltr">{lifetime.invoice_count}{lifetime.cancelled_invoices ? ` (${t("analytics.cancelledCount", { count: lifetime.cancelled_invoices })})` : ""}</dd></div>
                <div><dt>{t("analytics.firstLatest")}</dt><dd dir="ltr">{when(lifetime.first_purchase_at)} → {when(lifetime.latest_purchase_at)}</dd></div>
                <div><dt>{t("analytics.rhythm")}</dt><dd dir="ltr">{lifetime.average_days_between_purchases ? t("analytics.everyDays", { days: lifetime.average_days_between_purchases }) : t("analytics.notEnough")}{lifetime.purchases_per_month ? ` · ${t("analytics.perMonth", { count: lifetime.purchases_per_month })}` : ""}</dd></div>
                <div><dt>{t("analytics.latePayments")}</dt><dd dir="ltr">{lifetime.overdue_threshold_days === null ? t("analytics.noThreshold") : lifetime.late_payment_count}</dd></div>
                <div><dt>{t("analytics.cancellationRequests")}</dt><dd dir="ltr">{lifetime.cancellation_requests}</dd></div>
              </dl>
              <div aria-label={t("analytics.lifetimeFinancial")} className="table-region" role="region" tabIndex={0}>
                <table className="order-lines" aria-label={t("analytics.lifetimeFinancial")}>
                  <thead><tr><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.totalPurchased")}</th><th>{t("analytics.largest")}</th><th>{t("analytics.average")}</th><th>{t("analytics.receipts")}</th><th>{t("analytics.customerOutstanding")}</th><th>{t("analytics.discounts")}</th><th>{t("analytics.markups")}</th></tr></thead>
                  <tbody>{lifetime.financial.map((row) => <tr key={row.currency}><td>{row.currency}</td><td dir="ltr"><bdi dir="ltr">{money(row.total_purchased, row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.largest_invoice ?? "—", row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.average_invoice ?? "—", row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.total_receipts, row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.outstanding, row.currency)}</bdi><bdi dir="ltr">{Number(row.credit) > 0 ? ` (${t("purchases.credit")} ${money(row.credit, row.currency)})` : ""}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.total_discounts, row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.total_markups, row.currency)}</bdi></td></tr>)}</tbody>
                </table>
              </div>
              <div className="lifetime-habits">
                <div><h5>{t("analytics.topProducts")}</h5><ol>{lifetime.top_products.map((row) => <li key={`${row.currency}-${row.name}`}>{row.name} · <bdi dir="ltr">{row.quantity}</bdi> · <bdi dir="ltr">{money(row.value, row.currency)}</bdi></li>)}</ol></div>
                <div><h5>{t("analytics.topCategories")}</h5><ol>{lifetime.top_categories.map((row) => <li key={`${row.currency}-${row.name}`}>{row.name} · <bdi dir="ltr">{money(row.value, row.currency)}</bdi></li>)}</ol></div>
                <div><h5>{t("analytics.gradeTimeline")}</h5><ol>{lifetime.grade_timeline.map((point) => <li key={point.at}><time dateTime={point.at}>{when(point.at)}</time> · {point.grade ?? "—"}</li>)}</ol></div>
                <div><h5>{t("analytics.monthlySpend")}</h5><ol>{lifetime.monthly_spend.map((row) => <li key={`${row.currency}-${row.month}`}><bdi dir="ltr">{row.month}</bdi> · <bdi dir="ltr">{money(row.amount, row.currency)}</bdi></li>)}</ol></div>
              </div>
            </>
          )}
        </div>
      ) : null}
      {flow ? (
        <>
          <h4>{t("analytics.eventFlow")}</h4>
          <p className="muted">{t("analytics.eventFlowBody")}</p>
          {flow.totals.length === 0 ? <p className="muted">—</p> : (
            <div aria-label={t("analytics.eventFlow")} className="table-region" role="region" tabIndex={0}>
              <table className="order-lines" aria-label={t("analytics.eventFlow")}>
                <thead><tr><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.confirmations")}</th><th>{t("analytics.editDeltas")}</th><th>{t("analytics.cancellations")}</th><th>{t("analytics.netEffect")}</th></tr></thead>
                <tbody>{flow.totals.map((row) => <tr key={row.currency}><td>{row.currency}</td><td dir="ltr"><bdi dir="ltr">{money(row.confirmations, row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.edit_deltas, row.currency)}</bdi></td><td dir="ltr"><bdi dir="ltr">{money(row.cancellations, row.currency)}</bdi></td><td dir="ltr"><strong><bdi dir="ltr">{money(row.net_effect, row.currency)}</bdi></strong></td></tr>)}</tbody>
              </table>
            </div>
          )}
          {flow.monthly.length ? (
            <table className="order-lines" aria-label={t("analytics.monthly")}>
              <thead><tr><th>{t("analytics.month")}</th><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.netEffect")}</th></tr></thead>
              <tbody>{flow.monthly.map((row) => <tr key={`${row.currency}-${row.month}`}><td dir="ltr">{row.month}</td><td>{row.currency}</td><td dir="ltr"><bdi dir="ltr">{money(row.net_effect, row.currency)}</bdi></td></tr>)}</tbody>
            </table>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
