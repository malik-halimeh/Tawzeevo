import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { SuspensionReason, Tenant, TenantListResponse, TenantStatus } from "../api/types";
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination, StatusBadge, SuccessNotice } from "../components/Ui";

interface AccessDraft {
  access_until: string;
  grace_until: string;
  reason: SuspensionReason;
}

export function TenantsPage() {
  const { i18n, t } = useTranslation();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | TenantStatus>((searchParams.get("status") as TenantStatus | null) ?? "");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Tenant>();
  const [notice, setNotice] = useState<string>();
  const [draft, setDraft] = useState<AccessDraft>({ access_until: "", grace_until: "", reason: "SUBSCRIPTION_OVERDUE" });
  const query = useQuery({
    queryKey: ["tenants", search, status, page],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), limit: "10" });
      if (search) params.set("search", search);
      if (status) params.set("status", status);
      return apiRequest<TenantListResponse>(`/api/v1/platform/tenants?${params}`);
    },
    placeholderData: keepPreviousData,
  });

  useEffect(() => {
    if (!selected) return;
    const fresh = query.data?.tenants.find((tenant) => tenant.id === selected.id);
    if (fresh) setSelected(fresh);
  }, [query.data, selected]);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["tenants"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
  };
  const setAccess = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("No tenant selected");
      if (!draft.access_until) throw new Error(t("tenants.accessRequired"));
      if (draft.grace_until && draft.grace_until < draft.access_until) throw new Error(t("applications.invalidGrace"));
      return apiRequest<Tenant>(`/api/v1/platform/tenants/${selected.id}/access-period`, {
        method: "PUT",
        body: JSON.stringify({ access_until: draft.access_until, grace_until: draft.grace_until || null }),
      });
    },
    onSuccess: async (tenant) => {
      setSelected(tenant);
      setNotice(t("tenants.accessSaved", { name: tenant.name }));
      await refresh();
    },
  });
  const suspend = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("No tenant selected");
      return apiRequest<Tenant>(`/api/v1/platform/tenants/${selected.id}/suspend`, { method: "POST", body: JSON.stringify({ reason: draft.reason }) });
    },
    onSuccess: async (tenant) => {
      setSelected(tenant);
      setNotice(t("tenants.suspended", { name: tenant.name }));
      await refresh();
    },
  });
  const reactivate = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("No tenant selected");
      if (draft.access_until && draft.grace_until && draft.grace_until < draft.access_until) throw new Error(t("applications.invalidGrace"));
      return apiRequest<Tenant>(`/api/v1/platform/tenants/${selected.id}/reactivate`, {
        method: "POST",
        body: JSON.stringify({ access_until: draft.access_until || null, grace_until: draft.grace_until || null }),
      });
    },
    onSuccess: async (tenant) => {
      setSelected(tenant);
      setNotice(t("tenants.reactivated", { name: tenant.name }));
      await refresh();
    },
  });
  const mutationError = setAccess.error ?? suspend.error ?? reactivate.error;
  const resetMutationState = () => {
    setAccess.reset();
    suspend.reset();
    reactivate.reset();
  };
  const openTenant = (tenant: Tenant) => {
    resetMutationState();
    setSelected(tenant);
    setNotice(undefined);
    setDraft({ access_until: tenant.access_until ?? "", grace_until: tenant.grace_until ?? "", reason: tenant.suspension_reason ?? "SUBSCRIPTION_OVERDUE" });
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow={t("tenants.eyebrow")} title={t("tenants.title")} description={t("tenants.description")} />
      {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); void query.refetch(); }}>
        <label className="field toolbar-search"><span>{t("common.search")}</span><input placeholder={t("tenants.searchPlaceholder")} value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <label className="field compact-field"><span>{t("fields.status")}</span><select value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="">{t("common.all")}</option><option value="ACTIVE">{t("status.ACTIVE")}</option><option value="SUSPENDED">{t("status.SUSPENDED")}</option><option value="CLOSED">{t("status.CLOSED")}</option></select></label>
        <button className="button button-secondary" type="submit">{t("common.search")}</button>
      </form>
      {selected ? (
        <section aria-labelledby="tenant-manage-title" className="content-card tenant-manage">
          <div className="review-summary"><div><p className="section-kicker">{t("tenants.manageKicker")}</p><h2 id="tenant-manage-title">{selected.name}</h2></div><div className="badge-pair"><StatusBadge value={selected.status} /><StatusBadge value={selected.access_status} /></div></div>
          {mutationError ? <ErrorState error={mutationError} /> : null}
          <div className="form-grid">
            <label className="field"><span>{t("fields.accessUntil")}</span><input type="date" value={draft.access_until} onChange={(event) => setDraft({ ...draft, access_until: event.target.value })} /></label>
            <label className="field"><span>{t("fields.graceUntil")}</span><input type="date" value={draft.grace_until} onChange={(event) => setDraft({ ...draft, grace_until: event.target.value })} /></label>
            <label className="field field-wide"><span>{t("fields.suspensionReason")}</span><select disabled={selected.status !== "ACTIVE"} value={draft.reason} onChange={(event) => setDraft({ ...draft, reason: event.target.value as SuspensionReason })}><option value="SUBSCRIPTION_OVERDUE">{t("reasons.SUBSCRIPTION_OVERDUE")}</option><option value="ADMINISTRATIVE">{t("reasons.ADMINISTRATIVE")}</option><option value="SECURITY">{t("reasons.SECURITY")}</option><option value="OTHER">{t("reasons.OTHER")}</option></select></label>
            <div className="form-actions field-wide"><button className="button button-secondary" onClick={() => setSelected(undefined)} type="button">{t("common.close")}</button><button className="button button-secondary" disabled={setAccess.isPending} onClick={() => { suspend.reset(); reactivate.reset(); setAccess.mutate(); }} type="button">{t("tenants.saveAccess")}</button>{selected.status === "ACTIVE" ? <button className="button button-danger" disabled={suspend.isPending} onClick={() => { setAccess.reset(); reactivate.reset(); suspend.mutate(); }} type="button">{t("tenants.suspend")}</button> : null}{selected.status === "SUSPENDED" ? <button className="button" disabled={reactivate.isPending} onClick={() => { setAccess.reset(); suspend.reset(); reactivate.mutate(); }} type="button">{t("tenants.reactivate")}</button> : null}</div>
          </div>
        </section>
      ) : null}
      {query.isPending ? <LoadingState /> : null}
      {query.error ? <ErrorState error={query.error} /> : null}
      {query.data && !query.data.tenants.length ? <EmptyState title={t("tenants.emptyTitle")} body={t("tenants.emptyBody")} /> : null}
      {query.data?.tenants.length ? (
        <section className="tenant-grid">
          {query.data.tenants.map((tenant) => (
            <article className="tenant-card" key={tenant.id}>
              <div className="tenant-card-top"><span className="tenant-monogram" aria-hidden="true">{tenant.name.slice(0, 2).toUpperCase()}</span><div className="badge-pair"><StatusBadge value={tenant.status} /><StatusBadge value={tenant.access_status} /></div></div>
              <h2>{tenant.name}</h2>
              <dl><div><dt>{t("fields.accessUntil")}</dt><dd>{tenant.access_until ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(`${tenant.access_until}T00:00:00`)) : t("tenants.noEndDate")}</dd></div><div><dt>{t("fields.graceUntil")}</dt><dd>{tenant.grace_until ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(`${tenant.grace_until}T00:00:00`)) : "—"}</dd></div></dl>
              <button className="text-link" onClick={() => openTenant(tenant)} type="button">{t("tenants.manage")}</button>
            </article>
          ))}
          <div className="tenant-pagination"><Pagination page={query.data.page} totalPages={query.data.total_pages} onPage={setPage} /></div>
        </section>
      ) : null}
    </div>
  );
}
