import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { API_BASE_URL, apiRequest } from "../api/client";
import { ErrorState } from "./Ui";

/**
 * Business branding (PHASE_08.md F): identity and contact, storefront theme and texts, invoice
 * presentation, localization defaults, logo. Presentation only — nothing here changes prices,
 * roles, ledgers or what the storefront is allowed to do.
 */
export interface Branding {
  tenant_id: string; business_name: string; description: string | null; phone: string | null; whatsapp: string | null; email: string | null; address: string | null;
  primary_color: string | null; secondary_color: string | null; storefront_title: string | null; banner_text: string | null; social_links: Record<string, string>;
  about_text: string | null; contact_text: string | null; privacy_text: string | null; terms_text: string | null;
  invoice_header: string | null; invoice_footer: string | null; invoice_terms: string | null; thank_you_text: string | null; invoice_qr_enabled: boolean;
  default_language: "en" | "ar"; date_format: string; timezone: string; display_currency: string | null; has_logo: boolean; logo_path: string | null; version: number;
}
type Draft = Record<string, string>;
const TEXT_KEYS = ["description", "phone", "whatsapp", "email", "address", "primary_color", "secondary_color", "storefront_title", "banner_text", "about_text", "contact_text", "privacy_text", "terms_text", "invoice_header", "invoice_footer", "invoice_terms", "thank_you_text"] as const;
const SOCIAL = ["instagram", "facebook", "tiktok", "website"] as const;

export function BrandingPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [branding, setBranding] = useState<Branding>();
  const [draft, setDraft] = useState<Draft>({});
  const [social, setSocial] = useState<Draft>({});
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [dateFormat, setDateFormat] = useState("DD/MM/YYYY");
  const [qr, setQr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();

  const apply = useCallback((body: Branding) => {
    setBranding(body);
    const next: Draft = {};
    for (const key of TEXT_KEYS) next[key] = body[key] ?? "";
    setDraft(next);
    setSocial(Object.fromEntries(SOCIAL.map((key) => [key, body.social_links[key] ?? ""])));
    setLanguage(body.default_language); setDateFormat(body.date_format); setQr(body.invoice_qr_enabled);
  }, []);
  useEffect(() => { apiRequest<Branding>(`/api/v1/tenants/${tenantId}/branding`).then(apply).catch(setError); }, [tenantId, apply]);

  const save = (event: FormEvent) => {
    event.preventDefault();
    if (!branding) return;
    setBusy(true); setError(undefined); setNotice(undefined);
    const body: Record<string, unknown> = { expected_version: branding.version || undefined, default_language: language, date_format: dateFormat, invoice_qr_enabled: qr, social_links: social };
    for (const key of TEXT_KEYS) body[key] = draft[key]?.trim() ? draft[key] : null;
    apiRequest<Branding>(`/api/v1/tenants/${tenantId}/branding`, { method: "PUT", body: JSON.stringify(body) })
      .then((saved) => { apply(saved); setNotice(t("branding.saved")); })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const uploadLogo = (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setError(undefined); setNotice(undefined);
    const form = new FormData(); form.append("file", file);
    apiRequest<Branding>(`/api/v1/tenants/${tenantId}/branding/logo`, { method: "POST", body: form })
      .then((saved) => { apply(saved); setNotice(t("branding.logoSaved")); })
      .catch(setError)
      .finally(() => setBusy(false));
  };
  const field = (key: typeof TEXT_KEYS[number], multiline = false, dir?: "ltr") => (
    <label className={`field${multiline ? " field-wide" : ""}`} key={key}><span>{t(`branding.fields.${key}`)}</span>
      {multiline ? <textarea dir={dir} rows={3} value={draft[key] ?? ""} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /> : <input dir={dir} value={draft[key] ?? ""} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} />}
    </label>
  );

  return (
    <section className="branding-panel" aria-labelledby="branding-title">
      <header>
        <p className="section-kicker">{t("branding.kicker")}</p>
        <h3 id="branding-title">{t("branding.title")}</h3>
        <p>{t("branding.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {notice ? <p className="form-status" role="status">{notice}</p> : null}
      {branding ? (
        <form className="form-grid branding-form" onSubmit={save}>
          <h4 className="field-wide">{t("branding.identity")} · {branding.business_name}</h4>
          <div className="field-wide logo-row">
            {branding.logo_path ? <img alt={t("branding.logoAlt", { name: branding.business_name })} className="branding-logo" src={`${API_BASE_URL}${branding.logo_path}`} /> : <span className="muted">{t("branding.noLogo")}</span>}
            <label className="field"><span>{t("branding.uploadLogo")}</span><input accept="image/png,image/jpeg,image/webp" disabled={busy} type="file" onChange={(event) => uploadLogo(event.target.files?.[0])} /></label>
          </div>
          {field("description", true)}{field("phone", false, "ltr")}{field("whatsapp", false, "ltr")}{field("email", false, "ltr")}{field("address")}
          <h4 className="field-wide">{t("branding.storefront")}</h4>
          {field("storefront_title")}{field("banner_text")}{field("primary_color", false, "ltr")}{field("secondary_color", false, "ltr")}
          {SOCIAL.map((key) => <label className="field" key={key}><span>{t(`branding.social.${key}`)}</span><input dir="ltr" placeholder="https://" value={social[key] ?? ""} onChange={(event) => setSocial({ ...social, [key]: event.target.value })} /></label>)}
          {field("about_text", true)}{field("contact_text", true)}{field("privacy_text", true)}{field("terms_text", true)}
          <h4 className="field-wide">{t("branding.invoice")}</h4>
          {field("invoice_header")}{field("invoice_footer")}{field("invoice_terms", true)}{field("thank_you_text")}
          <label className="field checkbox"><input checked={qr} type="checkbox" onChange={(event) => setQr(event.target.checked)} /> <span>{t("branding.qr")}</span></label>
          <h4 className="field-wide">{t("branding.localization")}</h4>
          <label className="field"><span>{t("branding.defaultLanguage")}</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value as "en" | "ar")}><option value="en">English</option><option value="ar">العربية</option></select>
          </label>
          <label className="field"><span>{t("branding.dateFormat")}</span>
            <select value={dateFormat} onChange={(event) => setDateFormat(event.target.value)}><option value="DD/MM/YYYY">DD/MM/YYYY</option><option value="YYYY-MM-DD">YYYY-MM-DD</option><option value="MM/DD/YYYY">MM/DD/YYYY</option></select>
          </label>
          <p className="muted field-wide">{t("branding.timezoneNote", { timezone: branding.timezone })}</p>
          <div className="field-wide"><button className="button" disabled={busy} type="submit">{t("common.saveChanges")}</button></div>
        </form>
      ) : null}
    </section>
  );
}
