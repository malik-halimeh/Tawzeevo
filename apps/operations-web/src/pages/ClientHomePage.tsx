import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { z } from "zod";

import { apiRequest } from "../api/client";
import type { TenantApplication, TenantContextListResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, FieldError, LoadingState, PageHeader, StatusBadge, SuccessNotice } from "../components/Ui";
import { TenantWorkspace } from "../components/TenantWorkspace";
import { takePendingApplication } from "./pendingApplication";

export function ClientHomePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [application, setApplication] = useState<TenantApplication>();
  const [requestError, setRequestError] = useState<unknown>();
  const tenantContexts = useQuery({
    queryKey: ["tenant-contexts"],
    queryFn: () => apiRequest<TenantContextListResponse>("/api/v1/tenant-contexts"),
    // After an application is sent from this page, look again now and then, so an approval opens
    // the workspace without a manual reload. Nothing is polled before that.
    refetchInterval: application ? 30_000 : false,
  });
  const tenants = tenantContexts.data?.tenants;
  // This person's own applications (D-111): one waiting for review is shown instead of the form.
  const mine = useQuery({
    queryKey: ["my-applications"],
    queryFn: () => apiRequest<TenantApplication[]>("/api/v1/tenant-applications/mine"),
    enabled: tenants !== undefined && tenants.length === 0,
  });
  const latest = application ?? mine.data?.[0];
  const waiting = latest?.status === "PENDING" ? latest : undefined;
  const schema = z.object({ business_name: z.string().trim().min(1, t("validation.required")).max(200) });
  const { formState: { errors, isSubmitting }, handleSubmit, register, reset, setValue } = useForm<{ business_name: string }>({ resolver: zodResolver(schema) });

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

  // A business name typed at registration is sent now, once, as this account's application (D-096);
  // if it cannot be sent the form keeps the name and shows why.
  const pendingHandled = useRef(false);
  useEffect(() => {
    if (pendingHandled.current || !tenants || tenants.length > 0 || application || (mine.data === undefined && !mine.isError)) return;
    pendingHandled.current = true;
    // Already waiting for review: the name typed at registration is not sent a second time.
    if (mine.data?.some((row) => row.status === "PENDING")) { takePendingApplication(); return; }
    const pending = takePendingApplication();
    if (!pending) return;
    setValue("business_name", pending);
    apiRequest<TenantApplication>("/api/v1/tenant-applications", { method: "POST", body: JSON.stringify({ business_name: pending }) })
      .then((submitted) => { setApplication(submitted); reset(); })
      .catch(setRequestError);
  }, [tenants, application, mine.data, mine.isError, reset, setValue]);

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
          <p className="muted">{t("clientHome.driverNote")}</p>
          {/* Once sent, the form gives way to the answer, so a second application is not invited. */}
          {waiting ? (
            <>
              <SuccessNotice>
                <span>{t("clientHome.applicationReceived", { name: waiting.business_name })}</span>
                <StatusBadge value={waiting.status} />
              </SuccessNotice>
              <p className="muted">{t("clientHome.applicationNext")}</p>
            </>
          ) : (
            <>
              {latest?.status === "REJECTED" ? (
                <div className="notice notice-warning" role="status">
                  <span>{t("clientHome.applicationNotApproved", { name: latest.business_name })}</span>
                  {latest.review_notes ? <small>{latest.review_notes}</small> : null}
                </div>
              ) : null}
              {requestError ? <ErrorState error={requestError} /> : null}
              <form className="inline-form" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
                <label className="field"><span>{t("fields.businessName")}</span><input {...register("business_name")} /><FieldError message={errors.business_name?.message} /></label>
                <button className="button" disabled={isSubmitting} type="submit">{isSubmitting ? t("common.sending") : t("clientHome.submitApplication")}</button>
              </form>
            </>
          )}
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
