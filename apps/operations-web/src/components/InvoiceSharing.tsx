import { useState } from "react";
import { useTranslation } from "react-i18next";

import { API_BASE_URL, apiRequest } from "../api/client";
import { ErrorState } from "./Ui";

interface LinkRecord {
  id: string;
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
}

interface IssuedLink extends LinkRecord {
  public_path: string;
  customer_phone: string | null;
  summary: string;
}

const copy = {
  en: {
    title: "Share invoice", manage: "Manage invoice links", create: "Create private link",
    rotate: "Replace link", revoke: "Revoke link", preview: "Open customer view",
    whatsapp: "Share on WhatsApp", expires: "Expires", revoked: "Revoked", expired: "Expired",
    description: "Anyone holding a link can view this invoice. Links expire after 90 days. Replacing a link revokes the old one.",
    once: "Copy or share this new link now. The secret cannot be retrieved later; replace the link if needed.",
    noPhone: "A valid customer phone snapshot is required for WhatsApp sharing.",
    empty: "No links have been created.", link: "Private invoice URL",
  },
  ar: {
    title: "مشاركة الفاتورة", manage: "إدارة روابط الفاتورة", create: "إنشاء رابط خاص",
    rotate: "استبدال الرابط", revoke: "إلغاء الرابط", preview: "فتح عرض العميل",
    whatsapp: "مشاركة عبر واتساب", expires: "تنتهي الصلاحية", revoked: "ملغى", expired: "منتهي",
    description: "يمكن لأي شخص يحمل الرابط عرض هذه الفاتورة. تنتهي الصلاحية بعد ٩٠ يوماً. استبدال الرابط يلغي القديم.",
    once: "انسخ أو شارك الرابط الجديد الآن. لا يمكن استرجاعه لاحقاً؛ استبدله عند الحاجة.",
    noPhone: "يلزم رقم هاتف عميل صالح محفوظ في الفاتورة للمشاركة عبر واتساب.",
    empty: "لم يتم إنشاء روابط.", link: "رابط الفاتورة الخاص",
  },
};

export function InvoiceSharing({ tenantId, invoiceId }: { tenantId: string; invoiceId: string }) {
  const { i18n } = useTranslation();
  const words = copy[i18n.language.startsWith("ar") ? "ar" : "en"];
  const [links, setLinks] = useState<LinkRecord[]>();
  const [issued, setIssued] = useState<IssuedLink>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const path = `/api/v1/invoices/${invoiceId}/capabilities`;
  const load = async () => setLinks(await apiRequest<LinkRecord[]>(`${path}?tenant_id=${tenantId}`));
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(undefined);
    try { await action(); } catch (problem) { setError(problem); } finally { setBusy(false); }
  };
  const issue = async (id?: string) => {
    const response = await apiRequest<IssuedLink>(
      `${path}${id ? `/${id}/rotate` : ""}?tenant_id=${tenantId}`, { method: "POST" },
    );
    setIssued(response);
    await load();
  };
  const revoke = async (id: string) => {
    await apiRequest(`${path}/${id}?tenant_id=${tenantId}`, { method: "DELETE" });
    if (issued?.id === id) setIssued(undefined);
    await load();
  };
  const url = issued ? `${API_BASE_URL}${issued.public_path}` : "";
  const whatsapp = issued?.customer_phone
    ? `https://wa.me/${issued.customer_phone.replace(/^\+/, "")}?text=${encodeURIComponent(`${issued.summary}\n${url}`)}`
    : undefined;

  return <section className="invoice-sharing" aria-label={words.title}>
    <h4>{words.title}</h4><p>{words.description}</p>
    <button className="text-button" disabled={busy} onClick={() => void run(load)} type="button">{words.manage}</button>
    {links ? <>
      <button className="button secondary-button" disabled={busy} onClick={() => void run(() => issue())} type="button">{words.create}</button>
      {links.length === 0 ? <p>{words.empty}</p> : null}
      {links.map(link => <article key={link.id} className="invoice-share-record">
        <span>{words.expires}: <time dateTime={link.expires_at}>{new Date(link.expires_at).toLocaleDateString(i18n.language)}</time></span>
        {link.revoked_at ? <strong>{words.revoked}</strong> : <>
          {new Date(link.expires_at) <= new Date() ? <span>{words.expired}</span> : null}
          <button className="text-button" disabled={busy} onClick={() => void run(() => issue(link.id))} type="button">{words.rotate}</button>
          <button className="text-button danger-link" disabled={busy} onClick={() => void run(() => revoke(link.id))} type="button">{words.revoke}</button>
        </>}
      </article>)}
    </> : null}
    {issued ? <div className="invoice-share-issued" role="status">
      <p>{words.once}</p>
      <label className="field"><span>{words.link}</span><input dir="ltr" readOnly value={url} onFocus={event => event.target.select()} /></label>
      <a href={url} target="_blank" rel="noopener noreferrer">{words.preview}</a>
      {whatsapp ? <a className="button" href={whatsapp} target="_blank" rel="noopener noreferrer">{words.whatsapp}</a> : <p>{words.noPhone}</p>}
    </div> : null}
    {error ? <ErrorState error={error} /> : null}
  </section>;
}
