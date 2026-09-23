import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { z } from "zod";

import { apiRequest } from "../api/client";
import type { TenantApplication, TenantContextListResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, FieldError, LoadingState, PageHeader, StatusBadge, SuccessNotice } from "../components/Ui";
import { TenantWorkspace } from "../components/TenantWorkspace";

export function ClientHomePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [application, setApplication] = useState<TenantApplication>();
  const [requestError, setRequestError] = useState<unknown>();
  const tenantContexts = useQuery({
    queryKey: ["tenant-contexts"],
    queryFn: () => apiRequest<TenantContextListResponse>("/api/v1/tenant-contexts"),
  });
  const tenants = tenantContexts.data?.tenants;
  const schema = z.object({ business_name: z.string().trim().min(1, t("validation.required")).max(200) });
  const { formState: { errors, isSubmitting }, handleSubmit, register, reset } = useForm<{ business_name: string }>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: { business_name: string }) => {
    setRequestError(undefined);
    try {
      const submitted = await apiRequest<TenantApplication>("/api/v1/tenant-applications", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setApplication(submitted);
      reset();
    } catch (error) {
      setRequestError(error);
    }
  };

  // A member of a business opens straight onto that workspace: its compact business header is the
  // page heading and follows the selected business, so no generic greeting or role summary sits
  // between the member and the day's work. The greeting stays for loading, errors and onboarding.
  if (tenants?.length) return <TenantWorkspace contexts={tenants} />;

  return (
    <div className="page-stack">
      <PageHeader eyebrow={t("clientHome.eyebrow")} title={t("clientHome.title", { name: user?.first_name })} {...(tenants ? { description: t("clientHome.description") } : {})} />
      {tenantContexts.isLoading ? <LoadingState /> : null}
      {tenantContexts.error ? <ErrorState error={tenantContexts.error} /> : null}
      {tenants && tenants.length === 0 ? <section className="workspace-grid">
        <article className="content-card application-invite">
          <p className="section-kicker">{t("clientHome.tenantApplication")}</p>
          <h2>{t("clientHome.applicationTitle")}</h2>
          <p>{t("clientHome.applicationBody")}</p>
          {application ? (
            <SuccessNotice>
              <span>{t("clientHome.applicationReceived", { name: application.business_name })}</span>
              <StatusBadge value={application.status} />
            </SuccessNotice>
          ) : null}
          {requestError ? <ErrorState error={requestError} /> : null}
          <form className="inline-form" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
            <label className="field"><span>{t("fields.businessName")}</span><input {...register("business_name")} /><FieldError message={errors.business_name?.message} /></label>
            <button className="button" disabled={isSubmitting} type="submit">{isSubmitting ? t("common.sending") : t("clientHome.submitApplication")}</button>
          </form>
        </article>
        <aside className="content-card next-stop-card">
          <p className="section-kicker">{t("clientHome.account")}</p>
          <h2>{t("clientHome.keepCurrent")}</h2>
          <p>{t("clientHome.profileBody")}</p>
          <Link className="text-link" to="/profile">{t("clientHome.editProfile")}</Link>
        </aside>
      </section> : null}
    </div>
  );
}
