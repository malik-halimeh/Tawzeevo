"use client";

import { useState } from "react";

import { shopHref } from "@/lib/format";
import { type Lang, t } from "@/lib/i18n";

type Step = "idle" | "sending" | "sent" | "confirming" | "done";

/** Send a one-time code to the customer's own phone, then enter it. The secrets never touch
 * this component: the routes under /{slug}/verify keep them in HttpOnly cookies. */
export function VerifyForm({ slug, lang, displayName, contactHint }: { slug: string; lang: Lang; displayName: string; contactHint: string }) {
  const [step, setStep] = useState<Step>("idle");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setStep("sending"); setError(null);
    const response = await fetch(`/${slug}/verify/start`, { method: "POST", headers: { "Accept-Language": lang } }).catch(() => null);
    const body = (await response?.json().catch(() => ({}))) as { ok?: boolean; code?: string | null } | undefined;
    if (body?.ok) { setStep("sent"); return; }
    setStep("idle");
    setError(t(lang, body?.code === "VERIFICATION_RATE_LIMITED" ? "verifyTooMany" : body?.code === "VERIFICATION_UNAVAILABLE" ? "verifyUnavailable" : "verifyFailed"));
  };
  const confirm = async () => {
    setStep("confirming"); setError(null);
    const response = await fetch(`/${slug}/verify/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }).catch(() => null);
    const body = (await response?.json().catch(() => ({}))) as { ok?: boolean; code?: string | null } | undefined;
    if (body?.ok) { setStep("done"); window.location.replace(shopHref(slug, lang)); return; }
    setStep("sent");
    setError(t(lang, body?.code === "VERIFICATION_RATE_LIMITED" ? "verifyTooMany" : "verifyWrongCode"));
  };

  return (
    <section className="verify" aria-labelledby="verify-title">
      <h2 id="verify-title">{t(lang, "verifyTitle", { name: displayName })}</h2>
      <p>{t(lang, "verifyBody", { hint: contactHint })}</p>
      {error ? <p className="notice notice-error" role="alert">{error}</p> : null}
      {step === "idle" || step === "sending" ? (
        <button className="add-button" disabled={step === "sending"} onClick={() => void send()} type="button">{t(lang, "verifySend")}</button>
      ) : (
        <form className="verify-form" onSubmit={(event) => { event.preventDefault(); void confirm(); }}>
          <p className="notice" role="status">{t(lang, "verifySent", { hint: contactHint })}</p>
          <label>
            <span>{t(lang, "verifyCode")}</span>
            <input autoComplete="one-time-code" dir="ltr" inputMode="numeric" maxLength={6} minLength={6} pattern="[0-9]{6}" required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} />
          </label>
          <div className="verify-actions">
            <button className="add-button" disabled={step === "confirming" || code.length < 6} type="submit">{t(lang, "verifyConfirm")}</button>
            <button className="link-button" disabled={step === "confirming"} onClick={() => void send()} type="button">{t(lang, "verifyResend")}</button>
          </div>
        </form>
      )}
    </section>
  );
}
