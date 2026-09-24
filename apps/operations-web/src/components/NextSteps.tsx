import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { Arrow } from "./Icon";
import { InvoiceSharing } from "./InvoiceSharing";
import { sectionHref } from "./workspaceSections";

/**
 * What an owner usually does after an invoice becomes official, from the same screen and without
 * choosing the customer or invoice again: open the invoice, share it, record a payment, create a
 * delivery. Each entry only opens an existing page with this invoice selected; that page applies
 * its own rules (the receipt and allocation rules, the delivery rules) exactly as when used alone.
 */
export function NextSteps({
  tenantId,
  invoice,
  showInvoice = true,
  showSharing = true,
  onRecordPayment,
}: {
  tenantId: string;
  invoice: { id: string; official_invoice_number: string | null };
  /** Off where the invoice itself is already the page (the invoice editor's document). */
  showInvoice?: boolean;
  showSharing?: boolean;
  /** When the payments page is already on screen (the invoice editor), switch to it in place. */
  onRecordPayment?: () => void;
}) {
  const { t } = useTranslation();
  const number = invoice.official_invoice_number ?? "…";
  const paymentHref = sectionHref("invoices", tenantId, { invoice: invoice.id, view: "payments" });
  return (
    <section aria-labelledby={`next-steps-${invoice.id}`} className="next-steps content-card">
      <h5 id={`next-steps-${invoice.id}`}>{t("nextSteps.title")}</h5>
      <ul className="next-steps-list">
        {showInvoice ? (
          <li>
            <span>{t("nextSteps.invoice")}</span>
            <Link to={sectionHref("invoices", tenantId, { invoice: invoice.id })}><bdi dir="ltr">{number}</bdi><Arrow small /></Link>
          </li>
        ) : null}
        <li>
          {onRecordPayment ? (
            <button className="button button-secondary" onClick={onRecordPayment} type="button">{t("nextSteps.recordPayment")}</button>
          ) : (
            <Link className="button button-secondary" to={paymentHref}>{t("nextSteps.recordPayment")}</Link>
          )}
          <Link className="button button-secondary" to={sectionHref("deliveries", tenantId, { invoice: invoice.id })}>{t("nextSteps.createDelivery")}</Link>
        </li>
      </ul>
      {showSharing ? <InvoiceSharing invoiceId={invoice.id} tenantId={tenantId} /> : null}
    </section>
  );
}
