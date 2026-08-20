import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { TenantApplicationListResponse, TenantListResponse } from "../api/types";
import { ErrorState, LoadingState, PageHeader } from "../components/Ui";

async function loadOverview() {
  const [users, applications, activeTenants, suspendedTenants] = await Promise.all([
    apiRequest<{ count: number }>("/stats/count"),
    apiRequest<TenantApplicationListResponse>("/api/v1/platform/tenant-applications?status=PENDING&limit=1"),
    apiRequest<TenantListResponse>("/api/v1/platform/tenants?status=ACTIVE&limit=100"),
    apiRequest<TenantListResponse>("/api/v1/platform/tenants?status=SUSPENDED&limit=100"),
  ]);
  return {
    users: users.count,
    pending: applications.total,
    active: activeTenants.total,
    suspended: suspendedTenants.total,
    overdue: [...activeTenants.tenants, ...suspendedTenants.tenants].filter(
      (tenant) => tenant.access_status === "overdue",
    ).length,
  };
}

export function AdminDashboardPage() {
  const { t } = useTranslation();
  const overview = useQuery({ queryKey: ["admin-overview"], queryFn: loadOverview });
  return (
    <div className="page-stack">
      <PageHeader eyebrow={t("admin.eyebrow")} title={t("admin.title")} description={t("admin.description")} />
      {overview.isPending ? <LoadingState /> : null}
      {overview.error ? <ErrorState error={overview.error} /> : null}
      {overview.data ? (
        <>
          <section aria-label={t("admin.summary")} className="dashboard-metrics">
            <article><span>{t("admin.activeUsers")}</span><strong>{overview.data.users}</strong><Link to="/admin/users">{t("common.manage")}</Link></article>
            <article className={overview.data.pending ? "metric-attention" : ""}><span>{t("admin.pendingApplications")}</span><strong>{overview.data.pending}</strong><Link to="/admin/applications">{t("common.review")}</Link></article>
            <article><span>{t("admin.activeTenants")}</span><strong>{overview.data.active}</strong><Link to="/admin/tenants">{t("common.manage")}</Link></article>
            <article><span>{t("admin.suspendedTenants")}</span><strong>{overview.data.suspended}</strong><Link to="/admin/tenants?status=SUSPENDED">{t("common.view")}</Link></article>
          </section>
          <section className="content-card route-brief">
            <div className="route-brief-marker"><span>{overview.data.overdue}</span><small>{t("admin.overdue")}</small></div>
            <div><p className="section-kicker">{t("admin.accessDesk")}</p><h2>{t("admin.accessTitle")}</h2><p>{overview.data.overdue ? t("admin.accessAttention", { count: overview.data.overdue }) : t("admin.accessClear")}</p></div>
            <Link className="button button-secondary" to="/admin/tenants">{t("admin.openTenantDesk")}</Link>
          </section>
        </>
      ) : null}
    </div>
  );
}
