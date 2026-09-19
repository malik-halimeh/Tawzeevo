import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { Customer, CustomerSearchResponse } from "../api/types";
import { ErrorState } from "./Ui";

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
      .then((body) => { setCustomers(body.customers); setCustomerId(body.customers.length === 1 ? body.customers[0]!.id : ""); })
      .catch(setError);
  };
  useEffect(() => {
    if (!customerId) { setLifetime(undefined); return; }
    apiRequest<Lifetime>(`/api/v1/analytics/customers/${customerId}?tenant_id=${tenantId}`).then(setLifetime).catch(setError);
  }, [customerId, tenantId]);
  const when = (value: string | null) => (value ? new Date(value).toLocaleDateString() : "—");

  const money = (rows: CurrencyAmount[]) => (rows.length ? rows.map((row) => `${row.amount} ${row.currency}`).join(" · ") : "—");
  const currencies = [...new Set([...(overview?.invoiced_sales ?? []), ...(overview?.customer_outstanding ?? []), ...(overview?.supplier_payable ?? [])].map((row) => row.currency))];

  return (
    <section className="analytics-panel" aria-labelledby="analytics-title">
      <header>
        <p className="section-kicker">{t("analytics.kicker")}</p>
        <h3 id="analytics-title">{t("analytics.title")}</h3>
        <p>{t("analytics.body")}</p>
      </header>
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
            <div><dt>{t("analytics.invoicedSales")}</dt><dd dir="ltr">{money(overview.invoiced_sales)}</dd></div>
            <div><dt>{t("analytics.receipts")}</dt><dd dir="ltr">{money(overview.customer_receipts)}</dd></div>
            <div><dt>{t("analytics.refunds")}</dt><dd dir="ltr">{money(overview.customer_refunds)}</dd></div>
            <div><dt>{t("analytics.customerOutstanding")}</dt><dd dir="ltr">{money(overview.customer_outstanding)}{overview.customer_credit.length ? ` (${t("purchases.credit")} ${money(overview.customer_credit)})` : ""}</dd></div>
            <div><dt>{t("analytics.supplierPayable")}</dt><dd dir="ltr">{money(overview.supplier_payable)}{overview.supplier_credit.length ? ` (${t("purchases.credit")} ${money(overview.supplier_credit)})` : ""}</dd></div>
          </dl>
          <h4>{t("analytics.profitTitle")}</h4>
          <p className="muted">{t("analytics.profitBody")}</p>
          {overview.gross_profit.length === 0 ? <p className="muted">—</p> : (
            <table className="order-lines" aria-label={t("analytics.profitTitle")}>
              <thead><tr><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.grossProfit")}</th><th>{t("analytics.coverage")}</th><th>{t("analytics.uncovered")}</th></tr></thead>
              <tbody>{overview.gross_profit.map((row) => <tr key={row.currency}><td>{row.currency}</td><td dir="ltr">{row.gross_profit}</td><td dir="ltr">{row.coverage_percent}% ({row.covered_lines}/{row.total_lines})</td><td dir="ltr">{row.uncovered_lines > 0 ? t("analytics.uncoveredLines", { count: row.uncovered_lines }) : t("analytics.allCovered")}</td></tr>)}</tbody>
            </table>
          )}
          {currencies.length > 1 ? <p className="muted">{t("analytics.noMixing")}</p> : null}
        </>
      ) : null}
      <h4>{t("analytics.lifetimeTitle")}</h4>
      <p className="muted">{t("analytics.lifetimeBody")}</p>
      <form className="inline-form" onSubmit={findCustomers}>
        <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" required value={phoneSearch} onChange={(event) => setPhoneSearch(event.target.value)} /></label>
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
      {phoneSearch && customers.length === 0 && !lifetime ? <p className="muted">{t("analytics.noCustomer")}</p> : null}
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
              <table className="order-lines" aria-label={t("analytics.lifetimeFinancial")}>
                <thead><tr><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.totalPurchased")}</th><th>{t("analytics.largest")}</th><th>{t("analytics.average")}</th><th>{t("analytics.receipts")}</th><th>{t("analytics.customerOutstanding")}</th><th>{t("analytics.discounts")}</th><th>{t("analytics.markups")}</th></tr></thead>
                <tbody>{lifetime.financial.map((row) => <tr key={row.currency}><td>{row.currency}</td><td dir="ltr">{row.total_purchased}</td><td dir="ltr">{row.largest_invoice ?? "—"}</td><td dir="ltr">{row.average_invoice ?? "—"}</td><td dir="ltr">{row.total_receipts}</td><td dir="ltr">{row.outstanding}{Number(row.credit) > 0 ? ` (${t("purchases.credit")} ${row.credit})` : ""}</td><td dir="ltr">{row.total_discounts}</td><td dir="ltr">{row.total_markups}</td></tr>)}</tbody>
              </table>
              <div className="lifetime-habits">
                <div><h5>{t("analytics.topProducts")}</h5><ol>{lifetime.top_products.map((row) => <li key={`${row.currency}-${row.name}`}>{row.name} · <bdi dir="ltr">{row.quantity}</bdi> · <bdi dir="ltr">{row.value} {row.currency}</bdi></li>)}</ol></div>
                <div><h5>{t("analytics.topCategories")}</h5><ol>{lifetime.top_categories.map((row) => <li key={`${row.currency}-${row.name}`}>{row.name} · <bdi dir="ltr">{row.value} {row.currency}</bdi></li>)}</ol></div>
                <div><h5>{t("analytics.gradeTimeline")}</h5><ol>{lifetime.grade_timeline.map((point) => <li key={point.at}><time dateTime={point.at}>{when(point.at)}</time> · {point.grade ?? "—"}</li>)}</ol></div>
                <div><h5>{t("analytics.monthlySpend")}</h5><ol>{lifetime.monthly_spend.map((row) => <li key={`${row.currency}-${row.month}`}><bdi dir="ltr">{row.month}</bdi> · <bdi dir="ltr">{row.amount} {row.currency}</bdi></li>)}</ol></div>
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
            <table className="order-lines" aria-label={t("analytics.eventFlow")}>
              <thead><tr><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.confirmations")}</th><th>{t("analytics.editDeltas")}</th><th>{t("analytics.cancellations")}</th><th>{t("analytics.netEffect")}</th></tr></thead>
              <tbody>{flow.totals.map((row) => <tr key={row.currency}><td>{row.currency}</td><td dir="ltr">{row.confirmations}</td><td dir="ltr">{row.edit_deltas}</td><td dir="ltr">{row.cancellations}</td><td dir="ltr"><strong>{row.net_effect}</strong></td></tr>)}</tbody>
            </table>
          )}
          {flow.monthly.length ? (
            <table className="order-lines" aria-label={t("analytics.monthly")}>
              <thead><tr><th>{t("analytics.month")}</th><th>{t("tenantWorkspace.currency")}</th><th>{t("analytics.netEffect")}</th></tr></thead>
              <tbody>{flow.monthly.map((row) => <tr key={`${row.currency}-${row.month}`}><td dir="ltr">{row.month}</td><td>{row.currency}</td><td dir="ltr">{row.net_effect}</td></tr>)}</tbody>
            </table>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
