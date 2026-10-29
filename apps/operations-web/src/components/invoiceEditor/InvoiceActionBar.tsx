import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

/**
 * The invoice's own buttons with its total beside them. Below 1024 px it stays at the bottom of
 * the screen, above the bottom navigation and the on-screen keyboard (invoiceEditorLayout.css).
 * It holds the editor's existing buttons themselves, so handlers and disabled rules are theirs.
 */
export function InvoiceActionBar({ figure, children, note }: {
  figure: { amount: string; currency: string; pending: boolean } | undefined;
  children: ReactNode;
  note?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div aria-label={t("invoiceEditorLayout.actions")} className="invoice-action-bar" role="group">
      <p className="invoice-action-total">
        <span>{figure ? t("invoiceEditorLayout.totalIn", { currency: figure.currency }) : t("invoiceEditorLayout.invoiceTotal")}{figure?.pending ? <small> · {t("invoiceEditorLayout.notSavedYet")}</small> : null}</span>
        <strong>{figure ? <bdi dir="ltr">{figure.amount}</bdi> : "—"}</strong>
      </p>
      {note}
      <div className="invoice-action-buttons">{children}</div>
    </div>
  );
}
