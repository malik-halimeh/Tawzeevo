import { useEffect, useState } from "react";
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
    title: "Share invoice", create: "Create private link",
    send: "Send on WhatsApp", sendReplace: "Replace link and send on WhatsApp",
    replaceNote: "Sending replaces the current link: the one sent before stops working.",
    rotate: "Replace link", revoke: "Revoke link", preview: "Open customer view",
    whatsapp: "Share on WhatsApp", expires: "Expires", revoked: "Revoked", expired: "Expired",
    description: "Anyone holding a link can view this invoice. Links expire after 90 days. Replacing a link revokes the old one.",
    once: "Copy or share this new link now. The secret cannot be retrieved later; replace the link if needed.",
    noPhone: "A valid customer phone snapshot is required for WhatsApp sharing.",
    empty: "No links have been created.", link: "Private invoice URL",
    copyLink: "Copy share link", copied: "Share link copied", copyFailed: "Copy did not work; select the link and copy it.",
  },
  ar: {
    title: "مشاركة الفاتورة", create: "إنشاء رابط خاص",
    send: "إرسال عبر واتساب", sendReplace: "استبدال الرابط والإرسال عبر واتساب",
    replaceNote: "الإرسال يستبدل الرابط الحالي: يتوقف الرابط المُرسل سابقاً عن العمل.",
    rotate: "استبدال الرابط", revoke: "إلغاء الرابط", preview: "فتح عرض العميل",
    whatsapp: "مشاركة عبر واتساب", expires: "تنتهي الصلاحية", revoked: "ملغى", expired: "منتهي",
    description: "يمكن لأي شخص يحمل الرابط عرض هذه الفاتورة. تنتهي الصلاحية بعد ٩٠ يوماً. استبدال الرابط يلغي القديم.",
    once: "انسخ أو شارك الرابط الجديد الآن. لا يمكن استرجاعه لاحقاً؛ استبدله عند الحاجة.",
    noPhone: "يلزم رقم هاتف عميل صالح محفوظ في الفاتورة للمشاركة عبر واتساب.",
    empty: "لم يتم إنشاء روابط.", link: "رابط الفاتورة الخاص",
    copyLink: "نسخ رابط المشاركة", copied: "تم نسخ رابط المشاركة", copyFailed: "تعذّر النسخ؛ حدّد الرابط وانسخه.",
  },
};

/** The WhatsApp share for an issued link, or undefined when the invoice has no customer phone. */
function waLink(link: IssuedLink): string | undefined {
  if (!link.customer_phone) return undefined;
  const url = `${API_BASE_URL}${link.public_path}`;
  return `https://wa.me/${link.customer_phone.replace(/^\+/, "")}?text=${encodeURIComponent(`${link.summary}\n${url}`)}`;
}

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
    return response;
  };
  // The links are listed as soon as the invoice is shown: nothing to open first.
  useEffect(() => {
    let live = true;
    apiRequest<LinkRecord[]>(`${path}?tenant_id=${tenantId}`)
      .then((rows) => { if (live) setLinks(Array.isArray(rows) ? rows : []); })
      .catch((problem: unknown) => { if (live) setError(problem); });
    return () => { live = false; };
  }, [path, tenantId]);
  const activeLink = links?.find((link) => !link.revoked_at && new Date(link.expires_at) > new Date());
  // One click: issue (or replace) the link, then open WhatsApp with it. The window is opened before
  // the request so the browser treats it as the owner's own click; without a phone it is closed and
  // the issued link stays on screen to copy.
  const sendOnWhatsApp = () => {
    const opened = window.open("", "_blank");
    if (opened) opened.opener = null;
    void run(async () => {
      try {
        const response = await issue(activeLink?.id);
        const target = waLink(response);
        if (target && opened) opened.location.href = target;
        else opened?.close();
      } catch (problem) {
        opened?.close();
        throw problem;
      }
    });
  };
  const revoke = async (id: string) => {
    await apiRequest(`${path}/${id}?tenant_id=${tenantId}`, { method: "DELETE" });
    if (issued?.id === id) setIssued(undefined);
    await load();
  };
  const url = issued ? `${API_BASE_URL}${issued.public_path}` : "";
  // The customer view opens without signing in and shows only this invoice (verified end to end),
  // so the copied link is the same share the WhatsApp button sends.
  const [copied, setCopied] = useState<"yes" | "failed" | null>(null);
  const copyLink = () => {
    if (!url) return;
    void (navigator.clipboard?.writeText(url) ?? Promise.reject(new Error("no clipboard"))).then(() => setCopied("yes")).catch(() => setCopied("failed"));
  };
  const whatsapp = issued ? waLink(issued) : undefined;

  return <section className="invoice-sharing" aria-label={words.title}>
    <h4>{words.title}</h4><p>{words.description}</p>
    {links ? <>
      <button className="button button-send" disabled={busy} onClick={sendOnWhatsApp} type="button">{activeLink ? words.sendReplace : words.send}</button>
      {activeLink ? <p className="backend-note">{words.replaceNote}</p> : null}
      <button className="button secondary-button" disabled={busy} onClick={() => void run(async () => { await issue(); })} type="button">{words.create}</button>
      {links.length === 0 ? <p>{words.empty}</p> : null}
      {links.map(link => <article key={link.id} className="invoice-share-record">
        <span>{words.expires}: <time dateTime={link.expires_at}>{new Date(link.expires_at).toLocaleDateString(i18n.language)}</time></span>
        {link.revoked_at ? <strong>{words.revoked}</strong> : <>
          {new Date(link.expires_at) <= new Date() ? <span>{words.expired}</span> : null}
          <button className="text-button" disabled={busy} onClick={() => void run(async () => { await issue(link.id); })} type="button">{words.rotate}</button>
          <button className="text-button danger-link" disabled={busy} onClick={() => void run(() => revoke(link.id))} type="button">{words.revoke}</button>
        </>}
      </article>)}
    </> : null}
    {issued ? <div className="invoice-share-issued" role="status">
      <p>{words.once}</p>
      <label className="field"><span>{words.link}</span><input dir="ltr" readOnly value={url} onFocus={event => event.target.select()} /></label>
      <button className="text-button" onClick={copyLink} type="button">{copied === "yes" ? words.copied : words.copyLink}</button>
      {copied === "failed" ? <p className="backend-note">{words.copyFailed}</p> : null}
      <a href={url} target="_blank" rel="noopener noreferrer">{words.preview}</a>
      {whatsapp ? <a className="button button-send" href={whatsapp} target="_blank" rel="noopener noreferrer">{words.whatsapp}</a> : <p>{words.noPhone}</p>}
    </div> : null}
    {error ? <ErrorState error={error} /> : null}
  </section>;
}
