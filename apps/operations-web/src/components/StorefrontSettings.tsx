import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { ErrorState } from "./Ui";

/**
 * Owner storefront settings (PHASE_05.md B; D-047): the public address, its rename with a kept
 * redirect, and how many products are currently visible to the public.
 */
export interface StorefrontSettingsResponse {
  slug: string;
  previous_slugs: string[];
  published_products: number;
  accepting_orders: boolean;
  customer_access_policy: string;
}

const STOREFRONT_BASE = (import.meta.env.VITE_STOREFRONT_BASE_URL as string | undefined) ?? "http://localhost:3000";

export function StorefrontSettings({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<StorefrontSettingsResponse>();
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const current = await apiRequest<StorefrontSettingsResponse>(`/api/v1/tenants/${tenantId}/storefront?tenant_id=${tenantId}`);
      setSettings(current);
      setSlug(current.slug);
    } catch (caught) {
      setError(caught);
    }
  }, [tenantId]);

  useEffect(() => { void refresh(); }, [refresh]);

  const rename = (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest<StorefrontSettingsResponse>(`/api/v1/tenants/${tenantId}/storefront/slug?tenant_id=${tenantId}`, {
      method: "PUT",
      body: JSON.stringify({ slug: slug.trim().toLowerCase() }),
    })
      .then((updated) => { setSettings(updated); setSlug(updated.slug); setNotice(t("storefront.renamed", { slug: updated.slug })); })
      .catch(setError)
      .finally(() => setBusy(false));
  };

  const url = settings ? `${STOREFRONT_BASE}/${settings.slug}` : "";
  const setPolicy = (policy: string) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    apiRequest<StorefrontSettingsResponse>(`/api/v1/tenants/${tenantId}/storefront/access-policy?tenant_id=${tenantId}`, { method: "PUT", body: JSON.stringify({ policy }) })
      .then((updated) => { setSettings(updated); setNotice(t("storefront.policySaved", { policy: t(`customerLink.policies.${updated.customer_access_policy}`) })); })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  return (
    <article className="content-card" aria-labelledby="storefront-settings-title">
      <p className="section-kicker">{t("storefront.kicker")}</p>
      <h3 id="storefront-settings-title">{t("storefront.title")}</h3>
      <p>{t("storefront.body")}</p>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      {settings ? (
        <dl className="sync-facts">
          <div><dt>{t("storefront.address")}</dt><dd><a dir="ltr" href={url} rel="noreferrer" target="_blank">{url}</a></dd></div>
          <div><dt>{t("storefront.published")}</dt><dd>{settings.published_products}</dd></div>
          <div><dt>{t("storefront.orders")}</dt><dd>{t(settings.accepting_orders ? "storefront.accepting" : "storefront.paused")}</dd></div>
          {settings.previous_slugs.length ? <div><dt>{t("storefront.previous")}</dt><dd dir="ltr">{settings.previous_slugs.join(", ")}</dd></div> : null}
          <div><dt>{t("storefront.policy")}</dt><dd>
            <select aria-label={t("storefront.policy")} disabled={busy} value={settings.customer_access_policy} onChange={(event) => setPolicy(event.target.value)}>
              <option value="LINK">{t("customerLink.policies.LINK")}</option>
              <option value="VERIFIED">{t("customerLink.policies.VERIFIED")}</option>
            </select>
            <p className="muted">{t("storefront.policyBody")}</p>
          </dd></div>
        </dl>
      ) : null}
      <form className="inline-form" onSubmit={rename}>
        <label className="field"><span>{t("storefront.slug")}</span><input dir="ltr" maxLength={50} minLength={3} pattern="[a-z0-9][a-z0-9-]{1,48}[a-z0-9]" required value={slug} onChange={(event) => setSlug(event.target.value)} /></label>
        <button className="button" disabled={busy || !settings || slug === settings.slug} type="submit">{t("storefront.rename")}</button>
      </form>
      <p className="muted">{t("storefront.renameNote")}</p>
    </article>
  );
}
