import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useState, useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { BusinessInvoiceListResponse, BusinessInvoiceListRow, InvoiceSummaryResponse } from "../api/types";
import "../invoicesFrontPage.css";
import { OwnerTodayStrip } from "./OwnerTodayStrip";
import { ErrorState, LoadingState } from "./Ui";
import { ChipRow } from "./listKit/ChipRow";
import { EmptyHint } from "./listKit/EmptyHint";
import { Fab } from "./listKit/Fab";
import { FilterSheet } from "./listKit/FilterSheet";
import { ListHeader } from "./listKit/ListHeader";
import { ListRow } from "./listKit/ListRow";
import { MonthGroup } from "./listKit/MonthGroup";
import { SortMenu } from "./listKit/SortMenu";
import { sectionHref } from "./workspaceSections";

const CHIPS = ["all", "unpaid", "overdue", "paid", "draft", "cancelled"] as const;
type InvoiceChip = (typeof CHIPS)[number];
const CHIP_PARAMS: Record<InvoiceChip, Record<string, string>> = {
  all: {}, unpaid: { paid_state: "OPEN" }, overdue: { overdue: "true" },
  paid: { paid_state: "PAID" }, draft: { status: "DRAFT" }, cancelled: { status: "CANCELLED" },
};
const EMPTY_FILTERS = { currency: "", date_from: "", date_to: "" };
const PAGE_SIZE = 20;
const BUSINESS_TIME_ZONE = "Asia/Beirut";
const monthFormatter = new Intl.DateTimeFormat("en-GB", { timeZone: BUSINESS_TIME_ZONE, year: "numeric", month: "2-digit" });

function subscribeConnection(onChange: () => void) {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => { window.removeEventListener("online", onChange); window.removeEventListener("offline", onChange); };
}
const offlineSnapshot = () => navigator.onLine === false;
const serverOfflineSnapshot = () => false;

/** The list projection owns no financial calculations or invoice commands. */
export function InvoicesFrontPage({ tenantId }: { tenantId: string }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [chip, setChip] = useState<InvoiceChip>("all");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS);
  const offline = useSyncExternalStore(subscribeConnection, offlineSnapshot, serverOfflineSnapshot);
  const params = new URLSearchParams({ tenant_id: tenantId, ...CHIP_PARAMS[chip] });
  for (const [name, value] of Object.entries(filters)) if (value) params.set(name, value);
  if (search.trim()) params.set("q", search.trim());
  const filterQuery = params.toString();

  // The overview always describes the whole business, independently of list filters.
  const summary = useQuery({
    queryKey: ["invoice-summary", tenantId],
    queryFn: () => apiRequest<InvoiceSummaryResponse>(`/api/v1/invoices/summary?tenant_id=${encodeURIComponent(tenantId)}`),
    placeholderData: keepPreviousData,
    retry: false,
    networkMode: "always",
  });
  const list = useInfiniteQuery({
    queryKey: ["business-invoices", tenantId, filterQuery],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => apiRequest<BusinessInvoiceListResponse>(`/api/v1/invoices/all?${filterQuery}&page=${pageParam}&limit=${PAGE_SIZE}`),
    getNextPageParam: (last) => last.page < last.total_pages ? last.page + 1 : undefined,
    retry: false,
    networkMode: "always",
  });
  // A revision between pages can move a row. Never show the same invoice twice.
  const rows = [...new Map((list.data?.pages.flatMap((page) => page.invoices) ?? []).map((row) => [row.id, row])).values()];
  const total = list.data?.pages[0]?.total;
  const groups = new Map<string, BusinessInvoiceListRow[]>();
  for (const row of rows) {
    const parts = monthFormatter.formatToParts(new Date(row.confirmed_at ?? row.created_at));
    const month = `${parts.find((part) => part.type === "year")?.value}-${parts.find((part) => part.type === "month")?.value}`;
    groups.set(month, [...(groups.get(month) ?? []), row]);
  }
  const needsConnection = offline || list.error instanceof TypeError || summary.error instanceof TypeError;
  const newInvoice = () => { void navigate(`${sectionHref("invoices", tenantId)}&fresh=${Date.now()}`); };
  const newLabel = t("invoicesFrontPage.newInvoice");
  const when = (value: string) => new Intl.DateTimeFormat(i18n.language === "ar" ? "ar-LB" : "en-GB", { timeZone: BUSINESS_TIME_ZONE }).format(new Date(value));

  function status(row: BusinessInvoiceListRow) {
    if (row.status === "DRAFT") return t("invoicesFrontPage.draft");
    if (row.status === "CANCELLED") return t("invoicesFrontPage.cancelled");
    if (row.is_overdue) return t("invoicesFrontPage.overdueDays", { days: row.overdue_age_days ?? 0 });
    if (row.paid_state === "PAID") return t("invoicesFrontPage.paid");
    if (row.paid_state === "PARTLY_PAID") return t("invoicesFrontPage.partlyPaid");
    return t("invoicesFrontPage.unpaid");
  }

  function showMoney(currency: string, next: InvoiceChip) {
    setChip(next);
    setFilters((current) => ({ ...current, currency }));
    setDraftFilters((current) => ({ ...current, currency }));
  }

  return (
    <div className="invoices-front-page" dir={i18n.dir()}>
      <ListHeader
        title={t("invoicesFrontPage.title")}
        count={total}
        countKey="invoicesFrontPage.count"
        onSearch={setSearch}
        searchLabel={t("invoicesFrontPage.search")}
        sort={<SortMenu value="newest" options={[{ value: "newest", label: t("invoicesFrontPage.newest") }]} onChange={() => undefined} />}
        actions={<button className="button" onClick={newInvoice} type="button">{newLabel}</button>}
      />
      <OwnerTodayStrip tenantId={tenantId} />
      <div aria-label={t("invoicesFrontPage.overview")} className="invoice-money-overview" role="group">
        {summary.data?.currencies.map((item) => (
          <section aria-label={item.currency} className="invoice-money-card" key={item.currency}>
            <h2><bdi dir="ltr">{item.currency}</bdi></h2>
            <button onClick={() => showMoney(item.currency, "unpaid")} type="button">
              <span>{t("invoicesFrontPage.owed")}</span>
              <bdi dir="ltr">{item.outstanding_total} {item.currency}</bdi>
              <small>{t("invoicesFrontPage.openInvoices", { count: item.open_count })}</small>
            </button>
            <button onClick={() => showMoney(item.currency, "overdue")} type="button">
              <span>{t("invoicesFrontPage.overdue")}</span>
              <bdi dir="ltr">{item.overdue_total} {item.currency}</bdi>
              <small>{t("invoicesFrontPage.overdueInvoices", { count: item.overdue_count })}</small>
            </button>
          </section>
        ))}
      </div>
      {summary.isPending ? <LoadingState /> : null}
      {summary.error && !(summary.error instanceof TypeError) && !offline ? <ErrorState error={summary.error} /> : null}
      <ChipRow chips={CHIPS.map((value) => ({ value, label: t(`invoicesFrontPage.${value}`) }))} label={t("invoicesFrontPage.chips")} value={chip} onChange={setChip} />
      <div className="invoice-list-tools">
        <FilterSheet
          activeCount={Object.values(filters).filter(Boolean).length}
          onApply={() => setFilters(draftFilters)}
          onClear={() => setDraftFilters(EMPTY_FILTERS)}
          onClose={() => setDraftFilters(filters)}
        >
          <label className="field"><span>{t("invoicesFrontPage.currency")}</span>
            <select value={draftFilters.currency} onChange={(event) => setDraftFilters({ ...draftFilters, currency: event.target.value })}>
              <option value="">{t("invoicesFrontPage.allCurrencies")}</option>
              {summary.data?.currencies.map(({ currency }) => <option key={currency} value={currency}>{currency}</option>)}
            </select>
          </label>
          <label className="field"><span>{t("invoicesFrontPage.dateFrom")}</span><input dir="ltr" type="date" max={draftFilters.date_to || undefined} value={draftFilters.date_from} onChange={(event) => setDraftFilters({ ...draftFilters, date_from: event.target.value })} /></label>
          <label className="field"><span>{t("invoicesFrontPage.dateTo")}</span><input dir="ltr" type="date" min={draftFilters.date_from || undefined} value={draftFilters.date_to} onChange={(event) => setDraftFilters({ ...draftFilters, date_to: event.target.value })} /></label>
        </FilterSheet>
      </div>
      {needsConnection ? <p className="notice" role="status">{t("invoicesFrontPage.offline")}</p> : null}
      {list.isPending ? <LoadingState /> : null}
      {list.error && !(list.error instanceof TypeError) && !offline ? <ErrorState error={list.error} /> : null}
      {list.error || summary.error ? <button className="button button-secondary" onClick={() => { if (list.error) void list.refetch(); if (summary.error) void summary.refetch(); }} type="button">{t("invoicesFrontPage.retry")}</button> : null}
      {list.isSuccess && !rows.length ? <EmptyHint text={t(`invoicesFrontPage.empty.${chip}`)} action={{ label: newLabel, onSelect: newInvoice }} /> : null}
      {[...groups].sort(([a], [b]) => b.localeCompare(a)).map(([month, invoices]) => (
        <MonthGroup key={month} month={month}>
          {invoices.map((row) => {
            const href = sectionHref("invoices", tenantId, { invoice: row.id });
            const actions = [{ label: t("invoicesFrontPage.open"), href }];
            if (row.status === "CONFIRMED" && Number(row.outstanding) > 0) actions.push({ label: t("invoicesFrontPage.recordPayment"), href: sectionHref("invoices", tenantId, { invoice: row.id, view: "payments" }) });
            return <ListRow key={row.id} href={href} title={row.customer_name ?? t("invoicesFrontPage.noCustomer")} subline={<><bdi dir="ltr">{row.official_invoice_number ?? t("invoicesFrontPage.draft")}</bdi>{" · "}<time dateTime={row.confirmed_at ?? row.created_at}>{when(row.confirmed_at ?? row.created_at)}</time></>} amount={`${row.total_due} ${row.currency}`} status={status(row)} actions={actions} />;
          })}
        </MonthGroup>
      ))}
      {total !== undefined ? <div className="invoice-list-paging">
        <p role="status">{t("invoicesFrontPage.shown", { shown: rows.length, total })}</p>
        {list.hasNextPage ? <button className="button button-secondary" disabled={list.isFetchingNextPage} onClick={() => { void list.fetchNextPage(); }} type="button">{t("invoicesFrontPage.loadMore")}</button> : null}
      </div> : null}
      <Fab label={newLabel} onSelect={newInvoice} />
    </div>
  );
}
