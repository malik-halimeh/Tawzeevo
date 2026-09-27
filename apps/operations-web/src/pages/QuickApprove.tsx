import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { TenantApplication } from "../api/types";

export const QUICK_ACCESS_DAYS = 30;

/** Today plus `days` as a calendar date (YYYY-MM-DD), the form the approve call takes. */
function calendarDatePlus(days: number, from = new Date()): string {
  const day = new Date(from.getFullYear(), from.getMonth(), from.getDate() + days);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

/**
 * "Approve (30 days)" (D-110): the existing approve call with access until today plus 30 days and no
 * grace date; the full review stays available for anything else. D-023 is unchanged.
 */
export function QuickApprove({ application, onDone }: { application: TenantApplication; onDone?: (application: TenantApplication) => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const approve = useMutation({
    mutationFn: () => apiRequest<TenantApplication>(`/api/v1/platform/tenant-applications/${application.id}/approve`, {
      method: "POST",
      body: JSON.stringify({ access_until: calendarDatePlus(QUICK_ACCESS_DAYS), grace_until: null, review_notes: null }),
    }),
    onSuccess: async (approved) => {
      onDone?.(approved);
      await Promise.all(["tenant-applications", "tenants", "admin-overview", "admin-pending"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
    },
  });
  return (
    <>
      <button className="button" disabled={approve.isPending || application.status !== "PENDING"} onClick={() => approve.mutate()} type="button">
        {t("applications.quickApprove", { days: QUICK_ACCESS_DAYS })}<span className="sr-only"> · {application.business_name}</span>
      </button>
      {approve.error ? <span className="field-error" role="alert">{approve.error instanceof Error ? approve.error.message : t("common.requestFailed")}</span> : null}
    </>
  );
}
