import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis } from "../api/types";
import { ErrorState } from "./Ui";
import { useKeepFocus } from "./useKeepFocus";

/**
 * Owner delivery desk (PHASE_07.md A/B/C/J; D-063). A sole owner sees "My deliveries" and is the
 * assignee by default; with drivers, the owner chooses and can reassign (audited). Completion and
 * cancellation are terminal; a mistaken completion gets a new task. Tasks never touch invoices.
 */
interface Assignee { membership_id: string; role: string; display_name: string; is_self: boolean }
interface Line { product_name: string; quantity: string; price_basis: ProductPriceBasis; pieces_per_box: number | null }
export interface Task {
  id: string; status: "ASSIGNED" | "COMPLETED" | "CANCELLED"; invoice_id: string; official_invoice_number: string | null; order_id: string | null; customer_id: string; customer_name: string; customer_phone: string; customer_address: string | null;
  customer_latitude: string | null; customer_longitude: string | null; assignee: Assignee; delivery_date: string | null; route_sequence: number | null; currency: string; amount_to_collect: string; items: Line[]; notes: string | null;
  completed_at: string | null; performed_by: Assignee | null; completion_note: string | null; cancelled_at: string | null; cancel_reason: string | null; version: number; created_at: string;
}
interface TaskList { tasks: Task[]; eligible_members: Assignee[]; sole_operator: boolean }
interface Member { id: string; role: string; is_active: boolean; display_name: string; email: string; is_self: boolean; revoked_at: string | null }
interface Eligible { invoice_id: string; official_invoice_number: string | null; customer_id: string; customer_name: string; currency: string; net_sales: string; confirmed_at: string | null; order_id: string | null; delivery_date: string | null }

export function DeliveryPanel({ tenantId }: { tenantId: string }) {
  const { t, i18n } = useTranslation();
  const q = `?tenant_id=${tenantId}`;
  const [data, setData] = useState<TaskList>();
  // Undefined until the first answer, so the invoice picker never says "nothing waiting" while it is loading.
  const [loadedEligible, setEligible] = useState<Eligible[]>();
  const eligible = loadedEligible ?? [];
  const [statusFilter, setStatusFilter] = useState<"ASSIGNED" | "COMPLETED" | "CANCELLED" | "">("ASSIGNED");
  const [invoiceId, setInvoiceId] = useState("");
  const [assignee, setAssignee] = useState("");
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [team, setTeam] = useState<Member[]>([]);
  const [driverEmail, setDriverEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const root = useRef<HTMLElement>(null);
  useKeepFocus(busy, root);

  const refresh = useCallback(async () => {
    const [list, open, team] = await Promise.all([
      apiRequest<TaskList>(`/api/v1/delivery-tasks${q}${statusFilter ? `&status=${statusFilter}` : ""}`),
      apiRequest<{ invoices: Eligible[] }>(`/api/v1/delivery-tasks/eligible-invoices${q}`),
      apiRequest<{ members: Member[] }>(`/api/v1/tenants/${tenantId}/memberships`),
    ]);
    setData(list); setEligible(open.invoices); setTeam(team.members);
  }, [q, statusFilter, tenantId]);
  useEffect(() => { refresh().catch(setError); }, [refresh]);

  const run = (action: () => Promise<string | undefined>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    action().then((message) => { if (message) setNotice(message); }).catch(setError).finally(() => { setBusy(false); refresh().catch(setError); });
  };
  const create = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      await apiRequest<Task>(`/api/v1/delivery-tasks${q}`, { method: "POST", body: JSON.stringify({ invoice_id: invoiceId, assigned_membership_id: assignee || null, delivery_date: date || null }) });
      setInvoiceId(""); setDate("");
      return t("delivery.created");
    });
  };
  const addDriver = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      await apiRequest<Member>(`/api/v1/tenants/${tenantId}/memberships`, { method: "POST", body: JSON.stringify({ email: driverEmail }) });
      setDriverEmail("");
      return t("delivery.driverAdded");
    });
  };
  const revoke = (member: Member) => run(async () => {
    await apiRequest<Member>(`/api/v1/tenants/${tenantId}/memberships/${member.id}/revoke`, { method: "POST" });
    return t("delivery.driverRevoked");
  });
  const act = (task: Task, path: string, body: Record<string, unknown>, message: string, method = "POST") => run(async () => {
    await apiRequest<Task>(`/api/v1/delivery-tasks/${task.id}${path}${q}`, { method, body: JSON.stringify({ expected_version: task.version, ...body }) });
    return message;
  });

  const when = (value: string | null) => (value ? new Date(value).toLocaleString(i18n.language === "ar" ? "ar-LB" : "en-GB") : "—");
  const members = data?.eligible_members ?? [];
  const sole = data?.sole_operator ?? true;
  const label = (person: Assignee) => `${person.display_name} · ${t(`procurement.roles.${person.role}`)}${person.is_self ? ` (${t("procurement.me")})` : ""}`;

  return (
    <section className="delivery-panel" aria-labelledby="delivery-title" ref={root}>
      <header>
        <p className="section-kicker">{t("delivery.kicker")}</p>
        <h3 id="delivery-title">{sole ? t("delivery.titleSole") : t("delivery.title")}</h3>
        <p>{sole ? t("delivery.bodySole") : t("delivery.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}

      <form className="inline-form delivery-create" onSubmit={create} aria-label={t("delivery.create")}>
        <label className="field"><span>{t("delivery.eligibleInvoice")}</span>
          <select required value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)}>
            <option value="">{loadedEligible === undefined ? t("common.loading") : eligible.length ? "—" : t("delivery.nothingEligible")}</option>
            {eligible.map((row) => <option key={row.invoice_id} value={row.invoice_id}>{row.official_invoice_number ?? "…"} · {row.customer_name} · {row.net_sales} {row.currency}{row.delivery_date ? ` · ${row.delivery_date}` : ""}</option>)}
          </select>
        </label>
        {!sole ? (
          <label className="field"><span>{t("delivery.assignTo")}</span>
            <select required value={assignee} onChange={(event) => setAssignee(event.target.value)}>
              <option value="">—</option>
              {members.map((person) => <option key={person.membership_id} value={person.membership_id}>{label(person)}</option>)}
            </select>
          </label>
        ) : null}
        <label className="field"><span>{t("orders.deliveryDate")}</span><input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
        <button className="button" disabled={busy || !invoiceId} type="submit">{t("delivery.create")}</button>
      </form>

      <div className="category-actions">
        <label className="field"><span>{t("procurement.state")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="ASSIGNED">{t("delivery.status.ASSIGNED")}</option>
            <option value="COMPLETED">{t("delivery.status.COMPLETED")}</option>
            <option value="CANCELLED">{t("delivery.status.CANCELLED")}</option>
            <option value="">{t("procurement.allLines")}</option>
          </select>
        </label>
        <label className="field field-wide"><span>{t("delivery.reason")}</span><input maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      </div>

      {data && data.tasks.length === 0 ? <p className="muted">{t("delivery.empty")}</p> : null}
      <details className="team">
        <summary>{t("delivery.team")}</summary>
        <p className="muted">{t("delivery.teamBody")}</p>
        <form className="inline-form" onSubmit={addDriver}>
          <label className="field"><span>{t("delivery.driverEmail")}</span><input required type="email" value={driverEmail} onChange={(event) => setDriverEmail(event.target.value)} /></label>
          <button className="button" disabled={busy} type="submit">{t("delivery.addDriver")}</button>
        </form>
        <ul className="outbox-list">
          {team.map((member) => (
            <li className="outbox-row" key={member.id}>
              <span>{member.display_name} · {t(`procurement.roles.${member.role}`)} · <bdi dir="ltr">{member.email}</bdi>{!member.is_active ? ` · ${t("delivery.revoked")}` : ""}</span>
              {member.is_active && !member.is_self ? <button className="text-button danger-link" disabled={busy} onClick={() => revoke(member)} type="button">{t("delivery.revoke")}</button> : null}
            </li>
          ))}
        </ul>
      </details>
      <ul className="outbox-list delivery-list" aria-label={t("delivery.list")}>
        {data?.tasks.map((task) => (
          <li className="outbox-row delivery-row" key={task.id}>
            <div>
              <strong>{task.customer_name}</strong> · <bdi dir="ltr">{task.customer_phone}</bdi>{task.customer_address ? ` · ${task.customer_address}` : ""}
              <div className="muted">
                <bdi dir="ltr">{task.official_invoice_number ?? "…"}</bdi> · {t("delivery.collect")}: <bdi dir="ltr">{task.amount_to_collect} {task.currency}</bdi>
                {task.delivery_date ? <> · <bdi dir="ltr">{task.delivery_date}</bdi></> : null} · {task.items.map((line) => `${line.quantity} × ${line.product_name}`).join(", ")}
              </div>
              <div className="muted">
                {t("delivery.assignedTo")}: {label(task.assignee)}
                {task.performed_by ? ` · ${t("delivery.doneBy")}: ${label(task.performed_by)} · ${when(task.completed_at)}${task.completion_note ? ` · ${task.completion_note}` : ""}` : ""}
                {task.cancel_reason ? ` · ${t("delivery.cancelledBecause", { reason: task.cancel_reason })}` : ""}
              </div>
              {task.status === "ASSIGNED" ? (
                <div className="category-actions">
                  {!sole ? (
                    <select aria-label={t("delivery.reassign", { customer: task.customer_name })} disabled={busy} value={task.assignee.membership_id} onChange={(event) => act(task, "/assignee", { assigned_membership_id: event.target.value }, t("delivery.reassigned"), "PUT")}>
                      {members.map((person) => <option key={person.membership_id} value={person.membership_id}>{label(person)}</option>)}
                    </select>
                  ) : null}
                  <button className="button" disabled={busy} onClick={() => act(task, "/complete", { note: reason || null }, t("delivery.completed"))} type="button">{t("delivery.complete")}</button>
                  <button className="text-button" disabled={busy || !reason.trim()} onClick={() => act(task, "/cancel", { reason }, t("delivery.cancelled"))} type="button">{t("delivery.cancel")}</button>
                </div>
              ) : null}
            </div>
            <span className="status-badge">{t(`delivery.status.${task.status}`)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
