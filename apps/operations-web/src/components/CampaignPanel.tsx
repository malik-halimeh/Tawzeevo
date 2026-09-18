import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { TenantProduct } from "../api/types";
import { ErrorState } from "./Ui";

/**
 * Featured-product campaigns (PHASE_05.md K): a chosen product is shown first on the storefront
 * for a window (7 days by default). Advertising only; it never says anything about availability.
 */
export interface Campaign {
  id: string;
  tenant_product_id: string;
  starts_at: string;
  ends_at: string;
  priority: number;
  created_at: string;
  cancelled_at: string | null;
  active: boolean;
}

export function CampaignPanel({ tenantId, products }: { tenantId: string; products: TenantProduct[] }) {
  const { t, i18n } = useTranslation();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [productId, setProductId] = useState("");
  const [priority, setPriority] = useState("0");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const result = await apiRequest<{ campaigns: Campaign[] }>(`/api/v1/tenants/${tenantId}/storefront/campaigns?tenant_id=${tenantId}`);
      setCampaigns(result.campaigns);
    } catch (caught) {
      setError(caught);
    }
  }, [tenantId]);

  useEffect(() => { void refresh(); }, [refresh]);

  const run = (action: () => Promise<string>) => {
    setBusy(true); setError(undefined); setNotice(undefined);
    action().then(setNotice).catch(setError).finally(() => { setBusy(false); void refresh(); });
  };

  const create = (event: FormEvent) => {
    event.preventDefault();
    run(async () => {
      const body: Record<string, unknown> = { product_id: productId, priority: Number(priority) || 0 };
      if (startsAt) body.starts_at = new Date(startsAt).toISOString();
      if (endsAt) body.ends_at = new Date(endsAt).toISOString();
      await apiRequest<Campaign>(`/api/v1/tenants/${tenantId}/storefront/campaigns?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify(body) });
      setStartsAt(""); setEndsAt(""); setPriority("0");
      return t("campaigns.created");
    });
  };
  const cancel = (campaign: Campaign) => run(async () => {
    await apiRequest<Campaign>(`/api/v1/tenants/${tenantId}/storefront/campaigns/${campaign.id}/cancel?tenant_id=${tenantId}`, { method: "POST" });
    return t("campaigns.cancelled");
  });

  const productName = (id: string) => products.find((product) => product.id === id)?.name ?? id.slice(0, 8);
  const when = (value: string) => new Date(value).toLocaleString(i18n.language === "ar" ? "ar-LB" : "en-GB");
  const state = (campaign: Campaign) => {
    if (campaign.cancelled_at) return t("campaigns.state.cancelled");
    if (campaign.active) return t("campaigns.state.active");
    return new Date(campaign.ends_at) <= new Date() ? t("campaigns.state.expired") : t("campaigns.state.scheduled");
  };

  return (
    <article className="content-card" aria-labelledby="campaigns-title">
      <p className="section-kicker">{t("campaigns.kicker")}</p>
      <h3 id="campaigns-title">{t("campaigns.title")}</h3>
      <p>{t("campaigns.body")}</p>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      <form className="form-grid" onSubmit={create}>
        <label className="field field-wide"><span>{t("campaigns.product")}</span>
          <select required value={productId} onChange={(event) => setProductId(event.target.value)}>
            <option value="">{t("campaigns.chooseProduct")}</option>
            {products.map((product) => <option key={product.id} value={product.id}>{product.name}{product.is_published ? "" : ` · ${t("campaigns.unpublished")}`}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("campaigns.priority")}</span><input inputMode="numeric" max={1000} min={0} type="number" value={priority} onChange={(event) => setPriority(event.target.value)} /></label>
        <label className="field"><span>{t("campaigns.startsAt")}</span><input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label>
        <label className="field"><span>{t("campaigns.endsAt")}</span><input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label>
        <div className="form-actions field-wide"><button className="button" disabled={busy || !productId} type="submit">{t("campaigns.feature")}</button></div>
      </form>
      <p className="muted">{t("campaigns.note")}</p>
      {campaigns.length === 0 ? <p className="muted">{t("campaigns.empty")}</p> : (
        <ul className="outbox-list">
          {campaigns.map((campaign) => (
            <li className="outbox-row" key={campaign.id}>
              <div>
                <strong>{productName(campaign.tenant_product_id)}</strong>
                <span className="status-badge">{state(campaign)}</span>
                <small dir="ltr"> {when(campaign.starts_at)} → {when(campaign.ends_at)} · {t("campaigns.priorityShort", { value: campaign.priority })}</small>
              </div>
              {!campaign.cancelled_at && new Date(campaign.ends_at) > new Date() ? <button className="text-button" disabled={busy} onClick={() => cancel(campaign)} type="button">{t("campaigns.cancel")}</button> : null}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
