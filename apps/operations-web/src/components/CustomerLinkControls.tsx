import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { ErrorState } from "./Ui";

/**
 * Personalized storefront link for one customer (PHASE_05.md C.1; D-071, D-072). The secret is
 * shown exactly once when issued; rotation kills the previous link at that instant; revocation
 * leaves the customer on the anonymous storefront. Only LINK is selectable in Phase 5.
 */
interface LinkRecord {
  id: string;
  customer_id: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  rotated_from_id: string | null;
}

interface LinkStatus {
  active: LinkRecord | null;
  effective_policy: string;
  policy_override: string | null;
  tenant_policy: string;
  available_policies: string[];
  verified_sessions: number;
}

const STOREFRONT_BASE = (import.meta.env.VITE_STOREFRONT_BASE_URL as string | undefined) ?? "http://localhost:3000";

export function CustomerLinkControls({ tenantId, customerId }: { tenantId: string; customerId: string }) {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<LinkStatus>();
  const [issuedUrl, setIssuedUrl] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await apiRequest<LinkStatus>(`/api/v1/tenants/${tenantId}/customers/${customerId}/access-link?tenant_id=${tenantId}`));
    } catch (caught) {
      setError(caught);
    }
  }, [tenantId, customerId]);

  useEffect(() => { void refresh(); }, [refresh]);

  const run = (action: () => Promise<void>) => {
    setBusy(true); setError(undefined); setCopied(false);
    action().catch(setError).finally(() => { setBusy(false); void refresh(); });
  };
  const issue = () => run(async () => {
    const issued = await apiRequest<LinkRecord & { storefront_path: string }>(`/api/v1/tenants/${tenantId}/customers/${customerId}/access-link?tenant_id=${tenantId}`, { method: "POST" });
    setIssuedUrl(`${STOREFRONT_BASE}${issued.storefront_path}`);
  });
  const setPolicy = (override: string) => run(async () => {
    setStatus(await apiRequest<LinkStatus>(`/api/v1/tenants/${tenantId}/customers/${customerId}/access-policy?tenant_id=${tenantId}`, { method: "PUT", body: JSON.stringify({ override: override || null }) }));
  });
  const endSessions = () => run(async () => {
    setStatus(await apiRequest<LinkStatus>(`/api/v1/tenants/${tenantId}/customers/${customerId}/verified-sessions/revoke?tenant_id=${tenantId}`, { method: "POST" }));
  });
  const revoke = () => run(async () => {
    await apiRequest<LinkRecord>(`/api/v1/tenants/${tenantId}/customers/${customerId}/access-link?tenant_id=${tenantId}`, { method: "DELETE" });
    setIssuedUrl(undefined);
  });
  const copy = () => {
    if (!issuedUrl) return;
    void navigator.clipboard?.writeText(issuedUrl).then(() => setCopied(true)).catch(() => setCopied(false));
  };
  const when = (value: string | null) => (value ? new Date(value).toLocaleString(i18n.language === "ar" ? "ar-LB" : "en-GB") : t("customerLink.never"));

  return (
    <div className="customer-link" aria-label={t("customerLink.title")}>
      <strong>{t("customerLink.title")}</strong>
      {error ? <ErrorState error={error} /> : null}
      {status ? (
        <p className="muted">
          {status.active ? t("customerLink.active", { issued: when(status.active.created_at), used: when(status.active.last_used_at) }) : t("customerLink.none")}
          {" · "}{t("customerLink.policy", { policy: t(`customerLink.policies.${status.effective_policy}`) })}
          {status.effective_policy === "VERIFIED" ? <> · {t("customerLink.verifiedSessions", { count: status.verified_sessions })}</> : null}
        </p>
      ) : null}
      {status ? (
        <label className="field"><span>{t("customerLink.override")}</span>
          <select disabled={busy} value={status.policy_override ?? ""} onChange={(event) => setPolicy(event.target.value)}>
            <option value="">{t("customerLink.overrideDefault", { policy: t(`customerLink.policies.${status.tenant_policy}`) })}</option>
            {status.available_policies.map((policy) => <option key={policy} value={policy}>{t(`customerLink.policies.${policy}`)}</option>)}
          </select>
        </label>
      ) : null}
      {issuedUrl ? (
        <div className="issued-link">
          <p className="form-status" role="status">{t("customerLink.showOnce")}</p>
          <input aria-label={t("customerLink.url")} dir="ltr" readOnly value={issuedUrl} onFocus={(event) => event.currentTarget.select()} />
          <button className="text-button" onClick={copy} type="button">{copied ? t("customerLink.copied") : t("customerLink.copy")}</button>
        </div>
      ) : null}
      <div className="category-actions">
        <button className="button" disabled={busy || !status} onClick={issue} type="button">{status?.active ? t("customerLink.rotate") : t("customerLink.issue")}</button>
        {status?.active ? <button className="text-button" disabled={busy} onClick={revoke} type="button">{t("customerLink.revoke")}</button> : null}
        {status && status.verified_sessions > 0 ? <button className="text-button" disabled={busy} onClick={endSessions} type="button">{t("customerLink.endSessions")}</button> : null}
      </div>
      <p className="muted">{t("customerLink.note")}</p>
    </div>
  );
}
