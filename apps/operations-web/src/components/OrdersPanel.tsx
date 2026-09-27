import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import { readLastChoice, rememberChoice } from "./lastChoice";
import { NextSteps } from "./NextSteps";
import { PENDING_ORDERS_KEY } from "./pendingOrders";
import { sectionHref } from "./workspaceSections";
import { ConfirmAction, ErrorState } from "./Ui";
import { useKeepFocus } from "./useKeepFocus";

/**
 * Storefront order inbox and review (PHASE_05.md G–J; D-046, D-049, D-072, D-090). An order placed
 * through a personalized link arrives already linked to that customer; a public order is linked by
 * the owner explicitly. The owner confirms through the Phase 3 confirmation, declines, sets the
 * delivery date after confirmation, and decides cancellation requests. A sole owner needs nothing else.
 */
export interface OrderSummary {
  id: string; status: "RECEIVED" | "CONFIRMED" | "DECLINED" | "CANCELLED"; contact_name: string; contact_phone: string;
  contact_address: string; notes: string | null; currency: string; intended_customer_id: string | null; intended_assurance: string | null;
  linked_customer_id: string | null; invoice_id: string | null; delivery_date: string | null; decision_note: string | null; created_at: string; decided_at: string | null;
}
interface Candidate { id: string; name: string; phone: string; grade: string | null; is_hint: boolean }
interface CancellationRequest { id: string; order_id: string; status: "PENDING" | "APPROVED" | "REJECTED"; reason: string | null; created_at: string; decided_at: string | null; decision_note: string | null }
interface InvoiceLine { id: string; product_name: string; quantity: string; effective_unit_price: string; line_total: string }
interface InvoiceView { id: string; status: string; current_revision_id: string; official_invoice_number: string | null; net_sales: string; currency: string; items: InvoiceLine[] }
interface OrderDelivery { id: string; status: "ASSIGNED" | "COMPLETED" | "CANCELLED"; delivery_date: string | null }
interface OrderDetail { order: OrderSummary; invoice: InvoiceView | null; candidates: Candidate[]; cancellation_requests: CancellationRequest[]; linked_customer_name?: string | null; deliveries?: OrderDelivery[] }

export function OrdersPanel({ tenantId, orderId = null }: { tenantId: string; orderId?: string | null }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  // Undefined until the first answer, so "no orders yet" is never shown while the inbox is still loading.
  const [loadedOrders, setOrders] = useState<OrderSummary[]>();
  const orders = loadedOrders ?? [];
  // The same meaning as the Orders badge: orders still awaiting the owner's decision.
  const awaiting = orders.filter((order) => order.status === "RECEIVED").length;
  const [selected, setSelected] = useState<OrderDetail>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const [grade, setGrade] = useState("");
  const [deliveryDate, setDeliveryDate] = useState("");
  const [note, setNote] = useState("");
  // "Confirm and schedule": the same three existing steps an owner takes by hand, in order.
  const [scheduleDate, setScheduleDate] = useState("");
  const [createTask, setCreateTask] = useState(true);
  const [assignee, setAssignee] = useState("");
  const [crew, setCrew] = useState<{ sole: boolean; members: { membership_id: string; display_name: string; role: string; is_self: boolean }[] }>();
  const root = useRef<HTMLElement>(null);
  useKeepFocus(busy, root);

  const base = `/api/v1/tenants/${tenantId}`;
  const q = `?tenant_id=${tenantId}`;

  const refresh = useCallback(async () => {
    try {
      const list = await apiRequest<{ orders: OrderSummary[] }>(`${base}/orders${q}`);
      setOrders(list.orders);
    } catch (caught) { setError(caught); }
  }, [base, q]);

  useEffect(() => { void refresh(); }, [refresh]);

  const open = useCallback(async (orderId: string) => {
    try {
      // The detail carries the invoice's current revision, so a confirm click always echoes the
      // revision produced by the latest link/re-pricing (stale ids are refused by Phase 3).
      const detail = await apiRequest<OrderDetail>(`${base}/orders/${orderId}${q}`);
      setSelected(detail);
      setDeliveryDate(detail.order.delivery_date ?? "");
    } catch (caught) { setError(caught); }
  }, [base, q]);

  // Opened from a link (the new-order notice, or a later resume): refresh the list, open that order.
  useEffect(() => {
    if (!orderId) return;
    void refresh();
    void open(orderId);
  }, [orderId, open, refresh]);

  const run = (action: () => Promise<string | undefined>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    action().then((message) => { if (message) setNotice(message); }).catch(setError).finally(() => {
      setBusy(false); void refresh(); if (selected) void open(selected.order.id);
      void queryClient.invalidateQueries({ queryKey: [PENDING_ORDERS_KEY] }); // the badge drops at once
    });
  };
  const link = (candidateId?: string) => run(async () => {
    if (!selected) return undefined;
    await apiRequest(`${base}/orders/${selected.order.id}/link-customer${q}`, { method: "POST", body: JSON.stringify(candidateId ? { customer_id: candidateId } : { create_from_snapshot: true, grade: grade || null }) });
    return t("orders.linked");
  });
  const confirm = () => run(async () => {
    if (!selected?.invoice) return undefined;
    await apiRequest(`${base}/orders/${selected.order.id}/confirm${q}`, { method: "POST", body: JSON.stringify({ expected_revision_id: selected.invoice.current_revision_id }) });
    return t("orders.confirmed");
  });
  const scheduling = selected?.order.status === "RECEIVED" && Boolean(selected.order.linked_customer_id) && Boolean(selected.invoice);
  useEffect(() => {
    if (!scheduling || crew) return;
    apiRequest<{ eligible_members: { membership_id: string; display_name: string; role: string; is_self: boolean }[]; sole_operator: boolean }>(`/api/v1/delivery-tasks${q}&status=ASSIGNED`)
      .then((list) => {
        setCrew({ sole: list.sole_operator, members: list.eligible_members });
        // The driver chosen last on this device starts selected while still assignable (D-103).
        const lastDriver = readLastChoice("driver", tenantId);
        if (lastDriver && list.eligible_members.some((person) => person.membership_id === lastDriver)) setAssignee((current) => current || lastDriver);
      })
      .catch(() => setCrew({ sole: true, members: [] }));
  }, [scheduling, crew, q, tenantId]);
  const confirmAndSchedule = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      if (!selected?.invoice) return undefined;
      const orderId = selected.order.id;
      const invoiceId = selected.invoice.id;
      await apiRequest(`${base}/orders/${orderId}/confirm${q}`, { method: "POST", body: JSON.stringify({ expected_revision_id: selected.invoice.current_revision_id }) });
      // From here the invoice is official whatever happens next; a later step that fails is named
      // and can be finished by hand below, exactly as without this shortcut.
      if (scheduleDate) {
        try {
          await apiRequest(`${base}/orders/${orderId}/delivery-date${q}`, { method: "PUT", body: JSON.stringify({ delivery_date: scheduleDate }) });
        } catch (problem) {
          setError(problem);
          return t("orders.schedule.partial", { step: t("orders.schedule.stepDate") });
        }
      }
      if (createTask) {
        try {
          await apiRequest(`/api/v1/delivery-tasks${q}`, { method: "POST", body: JSON.stringify({ invoice_id: invoiceId, assigned_membership_id: crew && !crew.sole ? assignee || null : null, delivery_date: scheduleDate || null }) });
          if (crew && !crew.sole && assignee) rememberChoice("driver", tenantId, assignee);
        } catch (problem) {
          setError(problem);
          return t("orders.schedule.partial", { step: t("orders.schedule.stepTask") });
        }
      }
      return t(scheduleDate && createTask ? "orders.schedule.doneBoth" : createTask ? "orders.schedule.doneTask" : scheduleDate ? "orders.schedule.doneDate" : "orders.confirmed");
    });
  };
  const decline = () => run(async () => {
    if (!selected) return undefined;
    await apiRequest(`${base}/orders/${selected.order.id}/decline${q}`, { method: "POST", body: JSON.stringify({ note: note || null }) });
    return t("orders.declined");
  });
  const setDate = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      if (!selected) return undefined;
      await apiRequest(`${base}/orders/${selected.order.id}/delivery-date${q}`, { method: "PUT", body: JSON.stringify({ delivery_date: deliveryDate }) });
      return t("orders.dateSaved");
    });
  };
  const decide = (requestId: string, approve: boolean) => run(async () => {
    await apiRequest(`${base}/orders/cancellation-requests/${requestId}/decide${q}`, { method: "POST", body: JSON.stringify({ approve, note: note || null }) });
    return t(approve ? "orders.cancellationApproved" : "orders.cancellationRejected");
  });

  const when = (value: string | null) => (value ? new Date(value).toLocaleString(i18n.language === "ar" ? "ar-LB" : "en-GB") : "—");
  const pending = selected?.cancellation_requests.find((row) => row.status === "PENDING");
  const invoice = selected?.invoice;

  return (
    <section className="orders-panel" aria-labelledby="orders-title" ref={root}>
      <header>
        <p className="section-kicker">{t("orders.kicker")}</p>
        <h3 id="orders-title">{t("orders.title")} {awaiting > 0 ? <span className="status-badge">{t("orders.awaiting", { count: awaiting })}</span> : null}</h3>
        <p>{t("orders.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      <div className="orders-layout">
        <ul className="outbox-list" aria-label={t("orders.inbox")}>
          {loadedOrders === undefined ? (error ? null : <li className="muted">{t("common.loading")}</li>) : orders.length === 0 ? <li className="muted">{t("orders.empty")}</li> : null}
          {orders.map((order) => (
            <li className="outbox-row" key={order.id}>
              <button aria-current={selected?.order.id === order.id ? "true" : undefined} className="text-button" onClick={() => { setError(undefined); setNotice(undefined); void open(order.id); }} type="button">
                <strong>{order.contact_name}</strong> · {when(order.created_at)}
              </button>
              <span className="status-badge">{t(`orders.status.${order.status}`)}</span>
            </li>
          ))}
        </ul>
        {selected ? (
          <article className="content-card order-detail" aria-label={t("orders.detail")}>
            <h4>{selected.order.contact_name} <span className="status-badge">{t(`orders.status.${selected.order.status}`)}</span></h4>
            <dl className="sync-facts">
              <div><dt>{t("fields.phone")}</dt><dd dir="ltr">{selected.order.contact_phone}</dd></div>
              <div><dt>{t("tenantWorkspace.address")}</dt><dd>{selected.order.contact_address}</dd></div>
              {selected.order.notes ? <div><dt>{t("orders.notes")}</dt><dd>{selected.order.notes}</dd></div> : null}
              {selected.order.intended_customer_id ? <div><dt>{t("orders.hint")}</dt><dd>{t("orders.hintBody", { assurance: selected.order.intended_assurance ?? "" })}</dd></div> : null}
              {selected.order.delivery_date ? <div><dt>{t("orders.deliveryDate")}</dt><dd>{selected.order.delivery_date}</dd></div> : null}
              {selected.order.decision_note ? <div><dt>{t("orders.decisionNote")}</dt><dd>{selected.order.decision_note}</dd></div> : null}
            </dl>
            {invoice ? (
              <table className="order-lines">
                <thead><tr><th>{t("orders.item")}</th><th>{t("invoiceEditor.quantity")}</th><th>{t("invoiceEditor.unitPrice")}</th><th>{t("orders.lineTotal")}</th></tr></thead>
                <tbody>{invoice.items.map((line) => <tr key={line.id}><td>{line.product_name}</td><td dir="ltr">{line.quantity}</td><td dir="ltr">{line.effective_unit_price}</td><td dir="ltr">{line.line_total}</td></tr>)}</tbody>
                <tfoot><tr><th colSpan={3}>{t("invoiceEditor.netSales")}</th><th dir="ltr">{invoice.net_sales} {invoice.currency}</th></tr></tfoot>
              </table>
            ) : null}

            {selected.order.status === "RECEIVED" ? (
              <div className="order-actions">
                {!selected.order.linked_customer_id ? (
                  <>
                    <h5>{t("orders.linkTitle")}</h5>
                    <p className="muted">{t("orders.linkBody")}</p>
                    <ul className="chips">
                      {selected.candidates.map((candidate) => (
                        <li key={candidate.id}><button className="text-button" disabled={busy} onClick={() => link(candidate.id)} type="button">{candidate.name} · <bdi dir="ltr">{candidate.phone}</bdi>{candidate.grade ? ` · ${candidate.grade}` : ""}{candidate.is_hint ? ` · ${t("orders.hintTag")}` : ""}</button></li>
                      ))}
                    </ul>
                    <form className="inline-form" onSubmit={(event) => { event.preventDefault(); link(); }}>
                      <label className="field"><span>{t("tenantWorkspace.grade")}</span>
                        <select value={grade} onChange={(event) => setGrade(event.target.value)}><option value="">—</option><option value="A+">A+</option><option value="A">A</option><option value="B+">B+</option><option value="B">B</option></select>
                      </label>
                      <button className="button" disabled={busy} type="submit">{t("orders.createFromSnapshot")}</button>
                    </form>
                  </>
                ) : (
                  <p className="form-status">{selected.linked_customer_name ? t("orders.linkedToName", { name: selected.linked_customer_name }) : t("orders.linkedTo")}</p>
                )}
                <div className="category-actions">
                  <button className="button" disabled={busy || !selected.order.linked_customer_id} onClick={confirm} type="button">{t("orders.confirm")}</button>
                  <label className="field"><span>{t("orders.noteLabel")}</span><input maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></label>
                  <ConfirmAction className="text-button danger-link" confirmLabel={t("orders.confirmDecline")} danger disabled={busy} label={t("orders.decline")} onConfirm={decline}>{t("orders.declineExplain")}</ConfirmAction>
                </div>
                <p className="muted">{t("orders.editNote")}</p>
                {scheduling ? (
                  <form aria-label={t("orders.schedule.title")} className="schedule-form" onSubmit={confirmAndSchedule}>
                    <h5>{t("orders.schedule.title")}</h5>
                    <p className="muted">{t("orders.schedule.body")}</p>
                    <label className="field"><span>{t("orders.deliveryDate")}</span><input type="date" value={scheduleDate} onChange={(event) => setScheduleDate(event.target.value)} /></label>
                    <label className="checkbox-row"><input checked={createTask} onChange={(event) => setCreateTask(event.target.checked)} type="checkbox" /><span>{t("orders.schedule.createTask")}</span></label>
                    {createTask && crew && !crew.sole ? (
                      <label className="field"><span>{t("delivery.assignTo")}</span>
                        <select required value={assignee} onChange={(event) => setAssignee(event.target.value)}>
                          <option value="">—</option>
                          {crew.members.map((person) => <option key={person.membership_id} value={person.membership_id}>{person.display_name}{person.is_self ? ` (${t("procurement.me")})` : ""}</option>)}
                        </select>
                      </label>
                    ) : null}
                    <button className="button" disabled={busy || (createTask && crew === undefined)} type="submit">{t("orders.schedule.submit")}</button>
                  </form>
                ) : null}
              </div>
            ) : null}

            {/* The official invoice and its delivery stay one click away, so the owner can stop and resume. */}
            {invoice?.official_invoice_number && selected.order.status !== "CONFIRMED" ? (
              <p className="order-links"><span>{t("nextSteps.linkedInvoice")}</span> <Link to={sectionHref("invoices", tenantId, { invoice: invoice.id })}><bdi dir="ltr">{invoice.official_invoice_number}</bdi></Link></p>
            ) : null}
            {selected.order.status === "CONFIRMED" && invoice ? <NextSteps invoice={invoice} tenantId={tenantId} /> : null}
            {selected.deliveries?.length ? (
              <ul aria-label={t("nextSteps.deliveries")} className="order-links">
                {selected.deliveries.map((task) => (
                  <li key={task.id}><Link to={sectionHref("deliveries", tenantId, { invoice: invoice?.id ?? null })}>{t("nextSteps.deliveries")} · {t(`delivery.status.${task.status}`)}{task.delivery_date ? <> · <bdi dir="ltr">{task.delivery_date}</bdi></> : null}</Link></li>
                ))}
              </ul>
            ) : null}

            {selected.order.status === "CONFIRMED" ? (
              <form className="inline-form" onSubmit={setDate}>
                <label className="field"><span>{t("orders.deliveryDate")}</span><input required type="date" value={deliveryDate} onChange={(event) => setDeliveryDate(event.target.value)} /></label>
                <button className="button" disabled={busy || !deliveryDate} type="submit">{t("orders.saveDate")}</button>
              </form>
            ) : null}

            {pending ? (
              <div className="notice notice-warning" role="status">
                <p>{t("orders.cancellationPending", { reason: pending.reason ?? "—" })}</p>
                <label className="field"><span>{t("orders.noteLabel")}</span><input maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></label>
                <div className="category-actions">
                  <ConfirmAction confirmLabel={t("orders.confirmApprove")} danger disabled={busy} label={t("orders.approveCancellation")} onConfirm={() => decide(pending.id, true)}>{t("orders.approveExplain")}</ConfirmAction>
                  <button className="text-button" disabled={busy} onClick={() => decide(pending.id, false)} type="button">{t("orders.rejectCancellation")}</button>
                </div>
              </div>
            ) : null}
            {selected.cancellation_requests.filter((row) => row.status !== "PENDING").map((row) => (
              <p className="muted" key={row.id}>{t(`orders.cancellationState.${row.status}`)} · {when(row.decided_at)}{row.decision_note ? ` · ${row.decision_note}` : ""}</p>
            ))}
          </article>
        ) : <p className="muted">{t("orders.pick")}</p>}
      </div>
    </section>
  );
}
