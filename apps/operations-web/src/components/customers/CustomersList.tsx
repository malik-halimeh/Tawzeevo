import { money } from "../../utils/money";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../../api/client";
import { type CustomerMatch, SUGGESTION_MIN_LENGTH } from "../invoiceEditor/customerSuggestions";
import { EmptyHint } from "../listKit/EmptyHint";
import { ListHeader } from "../listKit/ListHeader";
import { ListRow } from "../listKit/ListRow";
import { SortMenu } from "../listKit/SortMenu";
import { ErrorState } from "../Ui";
import { sectionHref } from "../workspaceSections";

type CustomerSort = "name" | "newest" | "owes_most";
interface CustomerPage {
  page: number; total: number; total_pages: number; customers: CustomerMatch[];
}

const QUERY_MAX_LENGTH = 64;

/** Owner server list. Search folding and sorting (including currencies) belong to the server. */
export function CustomersList({ tenantId, refreshKey, onEdit, onShopLink, onInvoices }: {
  tenantId: string;
  refreshKey: number;
  onEdit: (customer: CustomerMatch) => void;
  onShopLink: (customer: CustomerMatch) => void;
  onInvoices: (customer: CustomerMatch) => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<CustomerSort>("name");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CustomerPage>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);

  useEffect(() => { setPage(1); setData(undefined); }, [refreshKey]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(undefined);
    const params = new URLSearchParams({ sort, page: String(page), limit: "20" });
    if (query.length >= SUGGESTION_MIN_LENGTH) params.set("q", query);
    apiRequest<CustomerPage>(`/api/v1/tenants/${tenantId}/customers?${params}`)
      .then((body) => {
        if (!live) return;
        setData((previous) => ({ ...body, customers: page === 1 ? body.customers : [...(previous?.customers ?? []), ...body.customers] }));
      })
      .catch((problem: unknown) => { if (live) setError(problem); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [tenantId, query, sort, page, refreshKey, retry]);

  function reset() { setPage(1); setData(undefined); }

  return (
    <div className="customers-page-list">
      <ListHeader
        count={data?.total}
        countKey="customersPage.count"
        onSearch={(text) => {
          const typed = text.trim().slice(0, QUERY_MAX_LENGTH);
          const next = typed.length >= SUGGESTION_MIN_LENGTH ? typed : "";
          if (next !== query) { reset(); setQuery(next); }
        }}
        searchLabel={t("customersPage.search")}
        sort={<SortMenu onChange={(next) => { reset(); setSort(next); }} options={[
          { value: "name", label: t("customersPage.name") },
          { value: "newest", label: t("customersPage.newest") },
          { value: "owes_most", label: t("customersPage.owesMost") },
        ]} value={sort} />}
        title={t("tenantWorkspace.customers")}
      />
      {error ? <><ErrorState error={error} /><button className="button button-secondary" onClick={() => setRetry((value) => value + 1)} type="button">{t("customersPage.retry")}</button></> : null}
      {loading ? <p className="muted" role="status">{t("common.loading")}</p> : null}
      {data?.customers.length ? (
        <ul aria-label={t("allCustomers.title")} className="list-rows">
          {data.customers.map((customer) => (
            <ListRow
              actions={[
                { label: t("tenantWorkspace.newInvoice"), href: sectionHref("invoices", tenantId, { customer: customer.id }) },
                { label: t("tenantWorkspace.recordPayment"), href: sectionHref("invoices", tenantId, { customer: customer.id, view: "payments" }) },
                { label: t("common.edit"), onSelect: () => onEdit(customer) },
                { label: t("customersPage.shopLink"), onSelect: () => onShopLink(customer) },
                { label: t("allCustomers.invoices"), onSelect: () => onInvoices(customer) },
              ]}
              amount={customer.balances?.length ? customer.balances.map((balance) => <bdi className="customer-list-balance" dir="ltr" key={balance.currency}>{money(balance.balance, balance.currency)}</bdi>) : undefined}
              href={sectionHref("customers", tenantId, { customer: customer.id })}
              key={customer.id}
              subline={<><bdi className="customer-list-phone" dir="ltr">{customer.phone}</bdi>{customer.address || customer.grade ? <span className="customer-list-address">{customer.address || `${t("tenantWorkspace.grade")} ${customer.grade}`}</span> : null}</>}
              title={customer.name}
            />
          ))}
        </ul>
      ) : data && !loading && !error ? <EmptyHint text={t(query ? "customersPage.noMatches" : "allCustomers.empty")} /> : null}
      {data && page < data.total_pages ? <button className="button button-secondary" disabled={loading || Boolean(error)} onClick={() => setPage((value) => value + 1)} type="button">{t("customersPage.loadMore")}</button> : null}
    </div>
  );
}
