import { money } from "./format";
import { type Lang, t } from "./i18n";

/** One notification as the server sends it (D-114); the shop renders the text in the visitor's language. */
export interface CustomerNotification { id: string; kind: string; data: Record<string, string>; created_at: string; read: boolean }

export function notificationText(lang: Lang, item: CustomerNotification): string {
  if (item.kind === "PAYMENT_RECORDED") {
    return t(lang, "notificationPaymentRecorded", { amount: money(item.data.amount ?? "0", item.data.currency ?? ""), number: item.data.invoice_number || "—" });
  }
  return t(lang, "notificationGeneric");
}
