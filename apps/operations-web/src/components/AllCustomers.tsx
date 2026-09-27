import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { Customer } from "../api/types";
import { ErrorState, Pagination } from "./Ui";
import { sectionHref } from "./workspaceSections";

/**
 * Every customer of the business, 20 at a time, each with every invoice (D-101). Read-only lists:
 * an invoice opens in Invoices, where a draft is edited and a confirmed one is revised or cancelled
 * through the existing commands and their rules.
 */
interface CustomerPage { page: number; total_pages: number; total: number; customers: Customer[] }
interface InvoiceRow {
  id: string; status: "DRAFT" | "CONFIRMED" | "CANCELLED"; official_invoice_number: string | null; confirmed_at: string | null;
  created_at: string; currency: string; net_sales: string; total_due: string; server_revision_number: number;
}
interface InvoicePage { page: number; total_pages: number; total: number; invoices: InvoiceRow[] }

const PAGE_SIZE = 20;
const STATUS_KEY = { DRAFT: "invoiceEditor.draft", CONFIRMED: "invoiceEditor.confirmed", CANCELLED: "invoiceEditor.cancelled" } as const;

function CustomerInvoices({ tenantId, customer }: { tenantId: string; customer: Customer }) {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<InvoicePage>();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    let live = true;
    apiRequest<InvoicePage>(`/api/v1/invoices?tenant_id=${tenantId}&customer_id=${customer.id}&page=${page}&limit=${PAGE_SIZE}`)
      .then((body) => { if (live) { setData(body); setError(undefined); } })
      .catch((caught: unknown) => { if (live) setError(caught); });
    return () => { live = false; };
  }, [tenantId, customer.id, page]);
  const when = (value: string) => new Date(value).toLocaleDateString(i18n.language === "ar" ? "ar-LB" : "en-GB");
  if (error) return <ErrorState error={error} />;
  if (!data) return <p className="empty-note">{t("common.loading")}</p>;
  if (!data.invoices.length) return <p className="empty-note">{t("allCustomers.noInvoices")}</p>;
  return (
    <>
      <ul aria-label={t("allCustomers.invoicesOf", { name: customer.name })} className="customer-invoices">
        {data.invoices.map((invoice) => (
          <li key={invoice.id}>
            <Link to={sectionHref("invoices", tenantId, { invoice: invoice.id })}>
              <bdi dir="ltr">{invoice.official_invoice_number ?? `R${invoice.server_revision_number}`}</bdi>
            </Link>
            <span className={`status-badge status-${invoice.status.toLowerCase()}`}>{t(STATUS_KEY[invoice.status])}</span>
            <time dateTime={invoice.confirmed_at ?? invoice.created_at}>{when(invoice.confirmed_at ?? invoice.created_at)}</time>
            <bdi dir="ltr">{invoice.net_sales} {invoice.currency}</bdi>
          </li>
        ))}
      </ul>
      <Pagination onPage={setPage} page={page} totalPages={data.total_pages} />
    </>
  );
}

export function AllCustomers({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CustomerPage>();
  const [error, setError] = useState<unknown>();
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let live = true;
    apiRequest<CustomerPage>(`/api/v1/tenants/${tenantId}/customers?page=${page}&limit=${PAGE_SIZE}`)
      .then((body) => { if (live) { setData(body); setError(undefined); } })
      .catch((caught: unknown) => { if (live) setError(caught); });
    return () => { live = false; };
  }, [open, tenantId, page]);

  return (
    <details className="content-card all-customers" onToggle={(event) => setOpen(event.currentTarget.open)} open={open}>
      <summary>{t("allCustomers.title")}{data ? <span className="muted"> · {data.total}</span> : null}</summary>
      {error ? <ErrorState error={error} /> : null}
      {open && !data && !error ? <p className="empty-note">{t("common.loading")}</p> : null}
      {data && !data.customers.length ? <p className="empty-note">{t("allCustomers.empty")}</p> : null}
      {data?.customers.length ? (
        <ul aria-label={t("allCustomers.title")} className="all-customers-list">
          {data.customers.map((customer) => (
            <li key={customer.id}>
              <div className="all-customers-row">
                <span><strong>{customer.name}</strong> <small><bdi dir="ltr">{customer.phone}</bdi></small></span>
                <span className="all-customers-actions">
                  <Link className="text-button" to={sectionHref("customers", tenantId, { customer: customer.id })}>{t("allCustomers.openRecord")}</Link>
                  <button aria-expanded={expanded === customer.id} className="text-button" onClick={() => setExpanded(expanded === customer.id ? null : customer.id)} type="button">
                    {t("allCustomers.invoices")}<span className="sr-only"> · {customer.name}</span>
                  </button>
                </span>
              </div>
              {expanded === customer.id ? <CustomerInvoices customer={customer} tenantId={tenantId} /> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {data ? <Pagination onPage={(next) => { setExpanded(null); setPage(next); }} page={page} totalPages={data.total_pages} /> : null}
    </details>
  );
}
