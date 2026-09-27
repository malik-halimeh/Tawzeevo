import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";

/**
 * "Phone notifications" (D-116): web push for this browser. Permission is asked only when the
 * person presses Turn on. States: not supported here, blocked in the browser, on, off, or not
 * offered by this server (no keys configured).
 */
type State = "loading" | "unsupported" | "unavailable" | "denied" | "on" | "off";

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = `${base64url}${"=".repeat((4 - (base64url.length % 4)) % 4)}`.replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
  return bytes;
}

function supported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function PhoneNotifications() {
  const { t } = useTranslation();
  const [state, setState] = useState<State>("loading");
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  const refresh = useCallback(async () => {
    if (!supported()) { setState("unsupported"); return; }
    const server = await apiRequest<{ enabled: boolean; public_key: string | null }>("/api/v1/push/public-key");
    if (!server.enabled || !server.public_key) { setState("unavailable"); return; }
    setPublicKey(server.public_key);
    if (Notification.permission === "denied") { setState("denied"); return; }
    const registration = await navigator.serviceWorker.getRegistration();
    const subscription = await registration?.pushManager.getSubscription();
    if (!subscription) { setState("off"); return; }
    const answer = await apiRequest<{ subscribed: boolean }>("/api/v1/push/subscriptions/state", { method: "POST", body: JSON.stringify({ endpoint: subscription.endpoint }) });
    setState(answer.subscribed ? "on" : "off");
  }, []);

  useEffect(() => { refresh().catch(() => setState("unavailable")); }, [refresh]);

  const turnOn = async () => {
    if (!publicKey) return;
    setBusy(true); setError(false);
    try {
      const permission = await Notification.requestPermission(); // asked only here, on the click
      if (permission !== "granted") { setState(permission === "denied" ? "denied" : "off"); return; }
      const registration = await navigator.serviceWorker.ready;
      const subscription = (await registration.pushManager.getSubscription())
        ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) });
      await apiRequest("/api/v1/push/subscriptions", { method: "POST", body: JSON.stringify(subscription.toJSON()) });
      setState("on");
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    setBusy(true); setError(false);
    try {
      const registration = await navigator.serviceWorker.getRegistration();
      const subscription = await registration?.pushManager.getSubscription();
      if (subscription) {
        await apiRequest("/api/v1/push/subscriptions", { method: "DELETE", body: JSON.stringify({ endpoint: subscription.endpoint }) });
        await subscription.unsubscribe();
      }
      setState("off");
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") return null;
  return (
    <section aria-labelledby="phone-notifications-title" className="content-card phone-notifications">
      <h2 id="phone-notifications-title">{t("push.title")}</h2>
      <p className="muted">{t("push.body")}</p>
      <p role="status"><strong>{t(`push.states.${state}`)}</strong></p>
      {state === "off" ? <button className="button" disabled={busy} onClick={() => void turnOn()} type="button">{t("push.turnOn")}</button> : null}
      {state === "on" ? <button className="button button-secondary" disabled={busy} onClick={() => void turnOff()} type="button">{t("push.turnOff")}</button> : null}
      {error ? <p className="field-error" role="alert">{t("push.failed")}</p> : null}
      <p className="muted"><small>{t("push.iphone")}</small></p>
    </section>
  );
}
