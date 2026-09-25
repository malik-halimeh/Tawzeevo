import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import {
  COUNT_METRICS,
  type AnomalyItem,
  type CashFlowPeriod,
  type CurrencyCashFlow,
  type InactivityItem,
  type InactivityStatus,
  type PriorityItem,
  type Reason,
  type Scalar,
  useAnomalies,
  useCashFlow,
  useInactivity,
  usePriorities,
} from "../api/intelligence";
import { Arrow, Icon } from "./Icon";
import { ErrorState } from "./Ui";
import { sectionHref } from "./workspaceSections";

/**
 * Owner intelligence surfaces (D-089), placed beside the work they inform instead of on a page
 * of their own: today's priorities on Work, the attention list and a customer's signals in
 * Customers, cash position and unusual changes in Analytics. The API computes every figure from
 * the canonical records; nothing here adds, converts or estimates an amount. Scores are workflow
 * rankings and bands, never probabilities, and the cash view is history and position — the only
 * forward-looking figure is the labelled delivery projection.
 */
type T = TFunction;

/** An amount with its currency, isolated left-to-right so Arabic copy never reorders it. */
const money = (value: Scalar, currency: string) => `⁦${String(value)} ${currency}⁩`;
const num = (value: Scalar) => `⁦${String(value)}⁩`;

const BAND_TONE: Record<string, string> = { HIGH: "bad", MEDIUM: "warn", LOW: "" };
const RHYTHM_TONE: Record<string, string> = { LAPSED: "bad", AT_RISK: "bad", WATCH: "warn", NORMAL: "good", INSUFFICIENT_HISTORY: "" };
const ATTENTION: readonly string[] = ["HIGH", "MEDIUM"];
const OFF_RHYTHM: readonly InactivityStatus[] = ["WATCH", "AT_RISK", "LAPSED"];

function reasonText(t: T, reason: Reason, currency: string): string {
  const c = reason.context;
  switch (reason.code) {
    case "OLD_OVERDUE_BALANCE":
    case "OVERDUE_BALANCE":
      return t(`intelligence.reasons.${reason.code}`, { amount: money(reason.value, currency), days: num(c.overdue_age_days ?? null), threshold: num(c.threshold_days ?? null) });
    case "OUTSTANDING_BALANCE":
      return c.oldest_unpaid_age_days === null || c.oldest_unpaid_age_days === undefined
        ? t("intelligence.reasons.OUTSTANDING_BALANCE", { amount: money(reason.value, currency) })
        : t("intelligence.reasons.OUTSTANDING_BALANCE_AGE", { amount: money(reason.value, currency), days: num(c.oldest_unpaid_age_days) });
    case "PAST_NORMAL_PURCHASE_INTERVAL":
      return t("intelligence.reasons.PAST_NORMAL_PURCHASE_INTERVAL", { days: num(c.days_since_last_purchase ?? null), usual: num(c.median_purchase_interval_days ?? null) });
    case "ACTIVITY_DOWN_VS_90D":
      return t("intelligence.reasons.ACTIVITY_DOWN_VS_90D", { recent: money(c.sales_30d ?? null, currency), longer: money(c.sales_90d ?? null, currency) });
    case "INSUFFICIENT_PURCHASE_HISTORY":
    case "RECENT_CANCELLATIONS":
    case "RECENT_REVERSALS":
      return t(`intelligence.reasons.${reason.code}`, { count: Number(reason.value ?? 0) });
    default:
      return t("intelligence.reasons.OTHER", { code: reason.code });
  }
}

function Band({ band, score }: { band: string; score?: number }) {
  const { t } = useTranslation();
  return <span className={`badge ${BAND_TONE[band] ?? ""}`}>{t(`intelligence.band.${band}`)}{score === undefined ? null : <> · <bdi dir="ltr">{score}</bdi></>}</span>;
}

function Rhythm({ status }: { status: string }) {
  const { t } = useTranslation();
  return <span className={`badge ${RHYTHM_TONE[status] ?? ""}`}>{t(`intelligence.rhythm.${status}`)}</span>;
}

function rhythmLine(t: T, item: Pick<InactivityItem, "days_since_last_purchase" | "median_purchase_interval_days" | "invoice_count_lifetime" | "status">): string {
  if (item.status === "INSUFFICIENT_HISTORY" || item.median_purchase_interval_days === null) return t("intelligence.rhythmFew", { count: item.invoice_count_lifetime });
  return t("intelligence.rhythmLine", { days: num(item.days_since_last_purchase), usual: num(item.median_purchase_interval_days) });
}

/** A quiet inline failure for a supporting panel: it never displaces the owner's main work. */
function QuietError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { t } = useTranslation();
  return <div className="intel-quiet-error"><ErrorState error={error} /><button className="button button-secondary" onClick={onRetry} type="button"><Icon name="sync" small />{t("intelligence.retry")}</button></div>;
}

function Pending() {
  const { t } = useTranslation();
  // Not a live region: a supporting panel loading beside the main work should not be announced.
  return <p aria-busy="true" className="intel-pending muted"><span className="skeleton short" aria-hidden="true" />{t("intelligence.loading")}</p>;
}

/** Work: the few customers to act on today, above the day's stops and kept to one compact band. */
export function TodayBrief({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const priorities = usePriorities(tenantId);
  const anomalies = useAnomalies(tenantId);
  const attention = (priorities.data?.groups ?? []).flatMap((group) => group.items).filter((item) => ATTENTION.includes(item.band)).sort((a, b) => b.score - a.score);
  const unusual = (anomalies.data?.groups ?? []).reduce((count, group) => count + group.items.length, 0);
  return (
    <section aria-labelledby="today-brief-title" className="today-brief">
      <div className="section-title"><h2 id="today-brief-title">{t("intelligence.todayTitle")}</h2><Link className="text-btn" to={sectionHref("customers", tenantId)}>{t("intelligence.seeAll")}<Arrow small /></Link></div>
      {priorities.isPending ? <Pending /> : null}
      {priorities.error ? <QuietError error={priorities.error} onRetry={() => { void priorities.refetch(); }} /> : null}
      {priorities.data && attention.length === 0 ? <p className="muted empty-copy">{t("intelligence.todayEmpty")}</p> : null}
      {attention.length ? (
        <ol className="stop-list intel-list" aria-label={t("intelligence.todayTitle")}>
          {attention.slice(0, 3).map((item) => (
            <li className="stop-item" key={`${item.currency}-${item.customer_id}`}>
              <Link className="stop-button intel-row" to={sectionHref("customers", tenantId, { customer: item.customer_id })}>
                <span className="stop-copy"><strong>{item.customer_name}</strong><small>{t(`intelligence.action.${item.suggested_action_code}`)}</small>{item.reasons[0] ? <small>{reasonText(t, item.reasons[0], item.currency)}</small> : null}</span>
                <Band band={item.band} />
                <Arrow />
              </Link>
            </li>
          ))}
        </ol>
      ) : null}
      {attention.length > 3 ? <p className="muted intel-more">{t("intelligence.moreWaiting", { count: attention.length - 3 })}</p> : null}
      {unusual > 0 ? <p className="intel-unusual"><Icon name="info" small />{t("intelligence.unusualWeek", { count: unusual })} <Link to={sectionHref("analytics", tenantId)}>{t("intelligence.review")}</Link></p> : null}
    </section>
  );
}

function PriorityRow({ item, tenantId }: { item: PriorityItem; tenantId: string }) {
  const { t } = useTranslation();
  return (
    <li className="stop-item">
      <Link className="stop-button intel-row" to={sectionHref("customers", tenantId, { customer: item.customer_id })}>
        <span className="stop-copy">
          <strong>{item.customer_name}</strong>
          <small>{t(`intelligence.action.${item.suggested_action_code}`)}</small>
          {item.reasons.slice(0, 2).map((reason) => <small key={reason.code}>{reasonText(t, reason, item.currency)}</small>)}
        </span>
        <Band band={item.band} score={item.score} />
        <Arrow />
      </Link>
    </li>
  );
}

function RhythmRow({ item, tenantId }: { item: InactivityItem; tenantId: string }) {
  const { t } = useTranslation();
  return (
    <li className="stop-item">
      <Link className="stop-button intel-row" to={sectionHref("customers", tenantId, { customer: item.customer_id })}>
        <span className="stop-copy"><strong>{item.customer_name}</strong><small>{rhythmLine(t, item)}</small></span>
        <Rhythm status={item.status} />
        <Arrow />
      </Link>
    </li>
  );
}

/**
 * Customers: who needs attention (priorities) and whose buying rhythm has slipped (inactivity),
 * each ranked within its own currency. Opening a row opens that customer's record.
 */
export function AttentionList({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"priorities" | "rhythm">("priorities");
  const [showAll, setShowAll] = useState(false);
  const priorities = usePriorities(tenantId);
  const inactivity = useInactivity(tenantId, tab === "rhythm");
  const active = tab === "priorities" ? priorities : inactivity;
  const groups = tab === "priorities"
    ? (priorities.data?.groups ?? []).map((group) => ({ currency: group.currency, total: group.items.length, rows: group.items.filter((item) => showAll || ATTENTION.includes(item.band)).map((item) => <PriorityRow item={item} key={item.customer_id} tenantId={tenantId} />) }))
    : (inactivity.data?.groups ?? []).map((group) => ({ currency: group.currency, total: group.items.length, rows: group.items.filter((item) => showAll || OFF_RHYTHM.includes(item.status)).map((item) => <RhythmRow item={item} key={item.customer_id} tenantId={tenantId} />) }));
  const shown = groups.reduce((count, group) => count + group.rows.length, 0);
  const total = groups.reduce((count, group) => count + group.total, 0);
  const choose = (next: typeof tab) => { setTab(next); setShowAll(false); };
  return (
    <section aria-labelledby="attention-title" className="attention">
      <div className="section-title"><h2 id="attention-title">{t("intelligence.attentionTitle")}</h2></div>
      <p className="muted intel-intro">{t(tab === "priorities" ? "intelligence.attentionBody" : "intelligence.rhythmBody")}</p>
      <div className="segmented" role="group" aria-label={t("intelligence.attentionTitle")}>
        <button aria-pressed={tab === "priorities"} className="text-button" onClick={() => choose("priorities")} type="button">{t("intelligence.tabPriorities")}</button>
        <button aria-pressed={tab === "rhythm"} className="text-button" onClick={() => choose("rhythm")} type="button">{t("intelligence.tabRhythm")}</button>
      </div>
      {active.isPending ? <Pending /> : null}
      {active.error ? <QuietError error={active.error} onRetry={() => { void active.refetch(); }} /> : null}
      {active.data && total === 0 ? <p className="muted empty-copy">{t("intelligence.noHistory")}</p> : null}
      {active.data && total > 0 && shown === 0 ? <p className="muted empty-copy">{t(tab === "priorities" ? "intelligence.nothingUrgent" : "intelligence.allOnRhythm")}</p> : null}
      {groups.filter((group) => group.rows.length).map((group) => (
        <div className="intel-group" key={group.currency}>
          {groups.length > 1 ? <h3 className="intel-currency"><bdi dir="ltr">{group.currency}</bdi></h3> : null}
          <ol className="stop-list intel-list" aria-label={`${t(tab === "priorities" ? "intelligence.tabPriorities" : "intelligence.tabRhythm")} · ${group.currency}`}>{group.rows}</ol>
        </div>
      ))}
      {active.data && total > shown ? <button className="text-btn" onClick={() => setShowAll(true)} type="button">{t("intelligence.showAll", { count: total })}</button> : null}
      {groups.length > 1 ? <p className="muted">{t("analytics.noMixing")}</p> : null}
    </section>
  );
}

/** Customers › one record: why this customer is (or is not) on today's list, per currency. */
export function CustomerSignals({ tenantId, customerId }: { tenantId: string; customerId: string }) {
  const { t } = useTranslation();
  const priorities = usePriorities(tenantId);
  const inactivity = useInactivity(tenantId);
  const own = (priorities.data?.groups ?? []).flatMap((group) => group.items).filter((item) => item.customer_id === customerId);
  const rhythm = (inactivity.data?.groups ?? []).flatMap((group) => group.items).filter((item) => item.customer_id === customerId);
  const failed = priorities.error ?? inactivity.error;
  return (
    <section aria-labelledby="customer-signals-title" className="customer-signals">
      <h3 id="customer-signals-title">{t("intelligence.signalsTitle")}</h3>
      {priorities.isPending || inactivity.isPending ? <Pending /> : null}
      {failed ? <QuietError error={failed} onRetry={() => { void priorities.refetch(); void inactivity.refetch(); }} /> : null}
      {priorities.data && inactivity.data && own.length === 0 && rhythm.length === 0 ? <p className="muted">{t("intelligence.signalsNone")}</p> : null}
      {own.map((item) => {
        const cadence = rhythm.find((row) => row.currency === item.currency);
        return (
          <div className="signal" key={item.currency}>
            <div className="badge-pair"><bdi className="intel-currency-tag" dir="ltr">{item.currency}</bdi><Band band={item.band} score={item.score} /><Rhythm status={item.inactivity_status} /></div>
            <p className="signal-action"><strong>{t(`intelligence.action.${item.suggested_action_code}`)}</strong></p>
            {item.reasons.length ? <ul className="signal-reasons">{item.reasons.map((reason) => <li key={reason.code}>{reasonText(t, reason, item.currency)}</li>)}</ul> : null}
            {/* The rhythm line only when no listed reason already says it. */}
            {cadence && !item.reasons.some((reason) => reason.code === "PAST_NORMAL_PURCHASE_INTERVAL") ? <p className="muted signal-rhythm">{rhythmLine(t, cadence)}</p> : null}
          </div>
        );
      })}
      {own.length ? <p className="muted intel-footnote">{t("intelligence.scoreNote")}</p> : null}
    </section>
  );
}

const BUCKETS = ["AGE_0_30", "AGE_31_60", "AGE_61_90", "AGE_91_PLUS", "AGE_UNKNOWN"];

function CashCurrency({ row, threshold }: { row: CurrencyCashFlow; threshold: number | null }) {
  const { t } = useTranslation();
  const flow = row.historical_flow;
  const planned = row.planned_collections;
  const ageing = [...row.ageing].sort((a, b) => BUCKETS.indexOf(a.bucket) - BUCKETS.indexOf(b.bucket));
  return (
    <article className="cash-currency" aria-label={t("intelligence.cashIn", { currency: row.currency })}>
      <h5><bdi dir="ltr">{row.currency}</bdi></h5>
      <dl className="sync-facts analytics-facts">
        <div><dt>{t("intelligence.overdue")}</dt><dd>{threshold === null ? t("analytics.noThreshold") : t("intelligence.overdueOf", { overdue: money(row.position.overdue_receivables, row.currency), owed: money(row.position.customer_receivables, row.currency), count: row.position.overdue_customer_count })}</dd></div>
        <div><dt>{t("intelligence.collected")}</dt><dd>{money(flow.net_customer_collections, row.currency)}{Number(flow.customer_refunds) !== 0 ? ` · ${t("intelligence.refundsPaid", { amount: money(flow.customer_refunds, row.currency) })}` : ""}</dd></div>
        <div><dt>{t("intelligence.weekly")}</dt><dd>{flow.average_weekly_collections === null ? "—" : money(flow.average_weekly_collections, row.currency)}</dd></div>
        <div><dt>{t("intelligence.supplierPaid")}</dt><dd>{money(flow.supplier_payments, row.currency)}</dd></div>
      </dl>
      {ageing.length ? (
        <div aria-label={t("intelligence.ageingTitle", { currency: row.currency })} className="table-region" role="region" tabIndex={0}>
          <table className="order-lines" aria-label={t("intelligence.ageingTitle", { currency: row.currency })}>
            <thead><tr><th>{t("intelligence.ageBucket")}</th><th>{t("intelligence.amount")}</th><th>{t("intelligence.customersCount")}</th></tr></thead>
            <tbody>{ageing.map((bucket) => <tr key={bucket.bucket}><td>{t(`intelligence.bucket.${bucket.bucket}`)}</td><td dir="ltr">{bucket.amount} {row.currency}</td><td dir="ltr">{bucket.customer_count}</td></tr>)}</tbody>
          </table>
        </div>
      ) : <p className="muted">{t("intelligence.nothingOwed")}</p>}
      <p className="intel-projection">
        <Icon name="van" small />
        <span>{t("intelligence.planned", { amount: money(planned.amount, row.currency), count: planned.task_count, from: num(planned.from_date), through: num(planned.through_date) })}</span>
        <small>{t("intelligence.projectionNote")}</small>
      </p>
    </article>
  );
}

/** Analytics: where money stands and how it has moved, per currency. History and position only. */
export function CashFlowSection({ tenantId, period }: { tenantId: string; period: CashFlowPeriod }) {
  const { t } = useTranslation();
  const cash = useCashFlow(tenantId, period);
  return (
    <section aria-labelledby="cash-title" className="intel-cash">
      <h4 id="cash-title">{t("intelligence.cashTitle")}</h4>
      <p className="muted">{t("intelligence.cashBody")}</p>
      {cash.isPending ? <Pending /> : null}
      {cash.error ? <QuietError error={cash.error} onRetry={() => { void cash.refetch(); }} /> : null}
      {cash.data && cash.data.currencies.length === 0 ? <p className="muted">{t("intelligence.cashEmpty")}</p> : null}
      <div className="cash-grid">{cash.data?.currencies.map((row) => <CashCurrency key={row.currency} row={row} threshold={cash.data.overdue_threshold_days} />)}</div>
    </section>
  );
}

function anomalySummary(t: T, item: AnomalyItem, currency: string): string {
  const d = item.details;
  const value = COUNT_METRICS.has(item.metric) ? num(item.observed_value) : money(item.observed_value, currency);
  const usual = item.baseline.median === null ? null : COUNT_METRICS.has(item.metric) ? num(item.baseline.median) : money(item.baseline.median, currency);
  const who = typeof d.customer_name === "string" ? d.customer_name : t("intelligence.unnamedCustomer");
  switch (item.type) {
    case "OVERDUE_THRESHOLD_CROSSED":
      return t("intelligence.anomalyText.OVERDUE_THRESHOLD_CROSSED", { who, value, days: num(d.overdue_age_days ?? null), threshold: num(d.threshold_days ?? null) });
    case "BACKDATED_RECEIPT_LARGE":
      return t("intelligence.anomalyText.BACKDATED_RECEIPT_LARGE", { who, value, days: num(d.days_recorded_after_payment_date ?? null) });
    case "LINE_PRICE_BELOW_SNAPSHOT_COST":
      return t("intelligence.anomalyText.LINE_PRICE_BELOW_SNAPSHOT_COST", { product: String(d.product_name ?? ""), value, cost: usual ?? "—" });
    case "CUSTOMER_INVOICE_VALUE_HIGH":
      return t("intelligence.anomalyText.CUSTOMER_INVOICE_VALUE_HIGH", { who, value, usual: usual ?? "—" });
    default:
      return usual === null ? t("intelligence.anomalyText.observed", { value }) : t("intelligence.anomalyText.baseline", { value, usual });
  }
}

function anomalyLink(tenantId: string, item: AnomalyItem): string | null {
  if (!item.subject_id) return null;
  if (item.subject_type === "INVOICE") return sectionHref("invoices", tenantId, { invoice: item.subject_id });
  if (item.subject_type === "CUSTOMER") return sectionHref("customers", tenantId, { customer: item.subject_id });
  return null;
}

/** Analytics: values this week that sit far from the business's own history. Unusual, not wrong. */
export function AnomalySection({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const anomalies = useAnomalies(tenantId);
  const groups = anomalies.data?.groups ?? [];
  const found = groups.some((group) => group.items.length);
  return (
    <section aria-labelledby="unusual-title" className="intel-unusual-list">
      <h4 id="unusual-title">{t("intelligence.unusualTitle")}</h4>
      {anomalies.data ? <p className="muted">{t("intelligence.unusualBody", { timezone: anomalies.data.window.timezone, blocks: anomalies.data.window.baseline_blocks })}</p> : null}
      {anomalies.isPending ? <Pending /> : null}
      {anomalies.error ? <QuietError error={anomalies.error} onRetry={() => { void anomalies.refetch(); }} /> : null}
      {anomalies.data && !found ? <p className="muted empty-copy">{t("intelligence.unusualNone")}</p> : null}
      {groups.map((group) => (
        <div className="intel-group" key={group.currency}>
          {group.items.length ? (
            <ul className="ledger" aria-label={t("intelligence.unusualIn", { currency: group.currency })}>
              {group.items.map((item, index) => {
                const href = anomalyLink(tenantId, item);
                return (
                  <li key={`${item.type}-${item.subject_id ?? "tenant"}-${index}`}>
                    <span className="ledger-copy">
                      <strong>{t(`intelligence.anomaly.${item.type}`, { defaultValue: item.type })}</strong>
                      <small>{anomalySummary(t, item, group.currency)}</small>
                      {href ? <small><Link to={href}>{t(item.subject_type === "INVOICE" ? "intelligence.openInvoice" : "intelligence.openCustomer")}</Link></small> : null}
                    </span>
                    <bdi className="intel-currency-tag" dir="ltr">{group.currency}</bdi>
                    <span className={`badge ${item.severity === "HIGH" ? "bad" : "warn"}`}>{t(`intelligence.severity.${item.severity}`)}</span>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {group.insufficient_history.length ? <p className="muted intel-footnote">{t("intelligence.notYetChecked", { currency: group.currency, checks: group.insufficient_history.map((family) => t(`intelligence.family.${family}`, { defaultValue: family })).join(t("intelligence.listSeparator")) })}</p> : null}
        </div>
      ))}
    </section>
  );
}
