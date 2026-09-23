import type { ReactNode } from "react";
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
