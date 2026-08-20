import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { TenantApplication, TenantApplicationListResponse, TenantApplicationStatus } from "../api/types";
import { EmptyState, ErrorState, LoadingState, PageHeader, Pagination, StatusBadge, SuccessNotice } from "../components/Ui";

interface ReviewDraft {
  access_until: string;
  grace_until: string;
  review_notes: string;
}

const emptyReview: ReviewDraft = { access_until: "", grace_until: "", review_notes: "" };

export function ApplicationsPage() {
  const { i18n, t } = useTranslation();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<"" | TenantApplicationStatus>("PENDING");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<TenantApplication>();
  const [draft, setDraft] = useState<ReviewDraft>(emptyReview);
  const [notice, setNotice] = useState<string>();
  const query = useQuery({
    queryKey: ["tenant-applications", status, page],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), limit: "10" });
      if (status) params.set("status", status);
      return apiRequest<TenantApplicationListResponse>(`/api/v1/platform/tenant-applications?${params}`);
    },
    placeholderData: keepPreviousData,
  });
  const review = useMutation({
    mutationFn: async (decision: "approve" | "reject") => {
      if (!selected) throw new Error("No application selected");
      if (draft.access_until && draft.grace_until && draft.grace_until < draft.access_until) {
        throw new Error(t("applications.invalidGrace"));
      }
      const payload = decision === "approve"
        ? {
            access_until: draft.access_until || null,
            grace_until: draft.grace_until || null,
            review_notes: draft.review_notes || null,
          }
        : { review_notes: draft.review_notes || null };
      return apiRequest<TenantApplication>(
        `/api/v1/platform/tenant-applications/${selected.id}/${decision}`,
        { method: "POST", body: JSON.stringify(payload) },
      );
    },
    onSuccess: async (application) => {
      setNotice(t(application.status === "APPROVED" ? "applications.approved" : "applications.rejected", { name: application.business_name }));
      setSelected(undefined);
      setDraft(emptyReview);
      await queryClient.invalidateQueries({ queryKey: ["tenant-applications"] });
      await queryClient.invalidateQueries({ queryKey: ["tenants"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
  });

  const openReview = (application: TenantApplication) => {
    setSelected(application);
    setDraft(emptyReview);
    setNotice(undefined);
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow={t("applications.eyebrow")} title={t("applications.title")} description={t("applications.description")} />
      {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}
      <div className="toolbar">
        <label className="field compact-field"><span>{t("fields.status")}</span><select value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setPage(1); }}><option value="">{t("common.all")}</option><option value="PENDING">{t("status.PENDING")}</option><option value="APPROVED">{t("status.APPROVED")}</option><option value="REJECTED">{t("status.REJECTED")}</option></select></label>
      </div>
      {selected ? (
        <section aria-labelledby="review-title" className="content-card review-panel">
          <div className="review-summary"><div><p className="section-kicker">{t("applications.reviewKicker")}</p><h2 id="review-title">{selected.business_name}</h2></div><StatusBadge value={selected.status} /></div>
          <dl className="compact-details"><div><dt>{t("applications.applicant")}</dt><dd dir="ltr">{selected.applicant_user_id}</dd></div><div><dt>{t("applications.submitted")}</dt><dd>{new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(selected.created_at))}</dd></div></dl>
          {review.error ? <ErrorState error={review.error} /> : null}
          <div className="form-grid">
            <label className="field"><span>{t("fields.accessUntil")}</span><input type="date" value={draft.access_until} onChange={(event) => setDraft({ ...draft, access_until: event.target.value })} /></label>
            <label className="field"><span>{t("fields.graceUntil")}</span><input type="date" value={draft.grace_until} onChange={(event) => setDraft({ ...draft, grace_until: event.target.value })} /></label>
            <label className="field field-wide"><span>{t("fields.reviewNotes")}</span><textarea rows={3} value={draft.review_notes} onChange={(event) => setDraft({ ...draft, review_notes: event.target.value })} /></label>
            <div className="form-actions field-wide"><button className="button button-secondary" onClick={() => setSelected(undefined)} type="button">{t("common.cancel")}</button><button className="button button-danger" disabled={review.isPending} onClick={() => review.mutate("reject")} type="button">{t("applications.reject")}</button><button className="button" disabled={review.isPending} onClick={() => review.mutate("approve")} type="button">{t("applications.approve")}</button></div>
          </div>
        </section>
      ) : null}
      {query.isPending ? <LoadingState /> : null}
      {query.error ? <ErrorState error={query.error} /> : null}
      {query.data && !query.data.applications.length ? <EmptyState title={t("applications.emptyTitle")} body={t("applications.emptyBody")} /> : null}
      {query.data?.applications.length ? (
        <section className="application-list">
          {query.data.applications.map((application) => (
            <article className="application-row" key={application.id}>
              <div className="application-route" aria-hidden="true"><span /></div>
              <div><div className="row-title"><h2>{application.business_name}</h2><StatusBadge value={application.status} /></div><p>{t("applications.submittedOn", { date: new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(application.created_at)) })}</p>{application.review_notes ? <small>{application.review_notes}</small> : null}</div>
              <button className="button button-secondary" disabled={application.status !== "PENDING"} onClick={() => openReview(application)} type="button">{application.status === "PENDING" ? t("common.review") : t("applications.reviewed")}</button>
            </article>
          ))}
          <Pagination page={query.data.page} totalPages={query.data.total_pages} onPage={setPage} />
        </section>
      ) : null}
    </div>
  );
}
