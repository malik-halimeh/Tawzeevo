import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
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

export function AnalyticsPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<PeriodKey>("30d");
  const [overview, setOverview] = useState<Overview>();
  const [flow, setFlow] = useState<Flow>();
  const [error, setError] = useState<unknown>();

  const load = useCallback(async () => {
    const [o, f] = await Promise.all([
      apiRequest<Overview>(`/api/v1/analytics/overview?tenant_id=${tenantId}&period=${period}`),
      apiRequest<Flow>(`/api/v1/analytics/events?tenant_id=${tenantId}&period=${period}`),
    ]);
    setOverview(o); setFlow(f);
  }, [tenantId, period]);
  useEffect(() => { load().catch(setError); }, [load]);

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
