import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { CustomerObligationListResponse } from "../api/types";
import { Arrow } from "./Icon";
import { PENDING_ORDERS_KEY, fetchPendingOrders } from "./pendingOrders";
import { PICKUP_REPORTS_KEY, fetchPendingPickups } from "./pickupReportsApi";
import { CollectionInbox } from "./CollectionInbox";
import { COLLECTION_REPORTS_KEY, fetchPendingCollections } from "./collectionReportsApi";
import { sectionHref } from "./workspaceSections";

/** The fields of a delivery used here (the owner's delivery list answer carries more). */
interface DeliveredTask { id: string; invoice_id: string; official_invoice_number: string | null; customer_id: string; customer_name: string; currency: string; completed_at: string | null }
interface Collection { task: DeliveredTask; outstanding: string }

const NEWEST_DELIVERIES = 50;
const SHOWN = 10;

/**
 * Delivered invoices whose amount is still open in the customer ledger. A completed delivery is never
 * a payment (D-063): this only lists what is still owed, from the existing delivery list and each
 * customer's open obligations, and links to the invoice's payments view where the receipt is recorded.
 */
async function fetchCollections(tenantId: string): Promise<Collection[]> {
  const list = await apiRequest<{ tasks: DeliveredTask[] }>(`/api/v1/delivery-tasks?tenant_id=${tenantId}&status=COMPLETED`);
  const newest = [...list.tasks].sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? "")).slice(0, NEWEST_DELIVERIES);
  const accounts = [...new Map(newest.map((task) => [`${task.customer_id}:${task.currency}`, task])).values()];
  const open = new Map<string, string>();
  await Promise.all(accounts.map(async (task) => {
    const answer = await apiRequest<CustomerObligationListResponse>(`/api/v1/payments/customers/${task.customer_id}/obligations?tenant_id=${tenantId}&currency=${task.currency}`);
    for (const row of answer.obligations) {
      if (row.source_type === "INVOICE" && row.source_id && Number(row.outstanding_amount) > 0) open.set(row.source_id, row.outstanding_amount);
    }
  }));
  return newest.filter((task) => open.has(task.invoice_id)).map((task) => ({ task, outstanding: open.get(task.invoice_id)! }));
}

/** The owner's "needs you now" strip on Today: orders waiting for review and collections to record. */
export function OwnerTodayStrip({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  // The shell polls the waiting orders; this reads the same cached answer and never fetches itself.
  const pending = useQuery({ queryKey: [PENDING_ORDERS_KEY, tenantId], queryFn: () => fetchPendingOrders(tenantId), enabled: false });
  const collections = useQuery({ queryKey: ["collections-to-record", tenantId], queryFn: () => fetchCollections(tenantId) });
  // Pickups a runner reported, waiting for the owner's confirmation (D-106).
  const pickups = useQuery({ queryKey: [PICKUP_REPORTS_KEY, tenantId], queryFn: () => fetchPendingPickups(tenantId) });
  const waiting = pending.data?.length ?? 0;
  const pickupCount = pickups.data?.length ?? 0;
  // Payments drivers reported at deliveries, waiting for confirmation (D-114).
  const reported = useQuery({ queryKey: [COLLECTION_REPORTS_KEY, tenantId], queryFn: () => fetchPendingCollections(tenantId) });
  const reportedCount = reported.data?.length ?? 0;
  const rows = collections.data ?? [];
  if (!waiting && !rows.length && !pickupCount && !reportedCount) return null;
  return (
    <section aria-labelledby="needs-you-title" className="owner-today">
      <h2 className="section-title" id="needs-you-title">{t("today.needsYou")}</h2>
      {waiting ? (
        <p className="owner-today-orders today-note" data-line="sales">
          <span>{t("orders.awaiting", { count: waiting })}</span>
          <Link to={sectionHref("orders", tenantId)}>{t("today.review")} <Arrow small /></Link>
        </p>
      ) : null}
      {reportedCount ? <div className="today-note today-note-wide" data-line="customers"><CollectionInbox tenantId={tenantId} /></div> : null}
      {pickupCount ? (
        <p className="owner-today-orders today-note" data-line="buying">
          <span>{t("pickupReport.toConfirm", { count: pickupCount })}</span>
          <Link to={sectionHref("procurement", tenantId)}>{t("today.review")} <Arrow small /></Link>
        </p>
      ) : null}
      {rows.length ? (
        <div className="today-note today-note-wide" data-line="customers">
          <h3>{t("today.collectionsTitle")}</h3>
          <ul aria-label={t("today.collectionsTitle")} className="owner-today-list">
            {rows.slice(0, SHOWN).map(({ task, outstanding }) => (
              <li key={task.id}>
                <span><strong>{task.customer_name}</strong> · <bdi dir="ltr">{task.official_invoice_number ?? "…"}</bdi></span>
                <bdi className="money" dir="ltr">{outstanding} {task.currency}</bdi>
                <Link className="money-link" to={sectionHref("invoices", tenantId, { invoice: task.invoice_id, view: "payments" })}>{t("tenantWorkspace.recordPayment")}</Link>
              </li>
            ))}
          </ul>
          {rows.length > SHOWN ? <p className="muted">{t("today.andMore", { count: rows.length - SHOWN })}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
