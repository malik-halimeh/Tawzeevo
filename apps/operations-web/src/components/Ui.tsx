import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";

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
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function LoadingState() {
  const { t } = useTranslation();
  return <div className="state-panel" role="status"><span className="spinner" />{t("common.loading")}</div>;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="state-panel empty-state">
      <span className="empty-route" aria-hidden="true" />
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
    </div>
  );
}

export function SuccessNotice({ children }: { children: ReactNode }) {
  return <div className="notice notice-success" role="status">{children}</div>;
}

export function FieldError({ message }: { message: string | undefined }) {
  return message ? <span className="field-error" role="alert">{message}</span> : null;
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
