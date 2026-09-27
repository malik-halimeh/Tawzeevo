import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import { Icon, type IconName } from "./Icon";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

/** Loading is shown as quiet placeholder bars plus text; nothing animates. */
export function LoadingState() {
  const { t } = useTranslation();
  return (
    <div className="state-panel loading-state" role="status">
      <span className="skeleton" aria-hidden="true" />
      <span className="skeleton short" aria-hidden="true" />
      <span>{t("common.loading")}</span>
    </div>
  );
}

export function EmptyState({ title, body, icon = "box" }: { title: string; body: string; icon?: IconName }) {
  return (
    <div className="empty-state">
      <Icon name={icon} />
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const message = error instanceof ApiError
    ? t(`errors.${error.code}`, { defaultValue: error.message })
    : error instanceof Error
      ? error.message
      : t("errors.UNKNOWN");
  return (
    <div className="notice notice-error" role="alert">
      <strong>{t("common.requestFailed")}</strong>
      <span>{message}</span>
      {error instanceof TypeError ? <small>{t("errors.NETWORK_UNREACHABLE")}</small> : null}
    </div>
  );
}

/**
 * A final action that asks once, inline (never a browser dialog): the first click shows what will
 * happen with a confirm button and "Keep"; only the confirm button runs `onConfirm`.
 */
export function ConfirmAction({ label, confirmLabel, onConfirm, disabled = false, danger = false, className, icon, children }: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
  danger?: boolean;
  className?: string;
  icon?: ReactNode;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const [armed, setArmed] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (armed) confirmButton.current?.focus(); }, [armed]);
  if (!armed) {
    return <button className={className ?? (danger ? "button button-danger" : "button")} disabled={disabled} onClick={() => setArmed(true)} ref={opener} type="button">{icon}{label}</button>;
  }
  return (
    <span aria-label={label} className="confirm-action" role="group">
      {children ? <span className="confirm-action-note">{children}</span> : null}
      <button className={danger ? "button button-danger" : "button"} disabled={disabled} onClick={() => { setArmed(false); onConfirm(); }} ref={confirmButton} type="button">{confirmLabel}</button>
      <button className="text-button" onClick={() => { setArmed(false); requestAnimationFrame(() => opener.current?.focus()); }} type="button">{t("common.keep")}</button>
    </span>
  );
}

const PAYMENT_METHODS = ["CASH", "CARD", "TRANSFER", "CHEQUE", "OTHER"] as const;

/** How money was paid, chosen from a short list instead of typed; a value saved before stays offered. */
export function PaymentMethodField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  const known = (PAYMENT_METHODS as readonly string[]).includes(value);
  return (
    <label className="field"><span>{t("invoiceEditor.paymentMethod")}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {PAYMENT_METHODS.map((method) => <option key={method} value={method}>{t(`invoiceEditor.methods.${method}`)}</option>)}
        {value && !known ? <option value={value}>{value}</option> : null}
      </select>
    </label>
  );
}

export function SuccessNotice({ children }: { children: ReactNode }) {
  return <div className="notice notice-success" role="status">{children}</div>;
}

export function FieldError({ message, id }: { message: string | undefined; id?: string | undefined }) {
  return message ? <span className="field-error" id={id} role="alert">{message}</span> : null;
}

export function StatusBadge({ value }: { value: string }) {
  const { t } = useTranslation();
  const normalized = value.toLowerCase();
  return <span className={`status-badge status-${normalized}`}>{t(`status.${value}`, { defaultValue: value })}</span>;
}

export function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  const { t } = useTranslation();
  if (totalPages <= 1) return null;
  return (
    <nav aria-label={t("pagination.label")} className="pagination">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)} type="button">
        {t("pagination.previous")}
      </button>
      <span>{t("pagination.page", { page, total: totalPages })}</span>
      <button disabled={page >= totalPages} onClick={() => onPage(page + 1)} type="button">
        {t("pagination.next")}
      </button>
    </nav>
  );
}
