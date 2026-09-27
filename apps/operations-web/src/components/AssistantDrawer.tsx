import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { CopilotPanel } from "./CopilotPanel";
import { Icon } from "./Icon";

/**
 * The business assistant beside every owner page (D-117): a side panel opened from the top bar, so a
 * question can be asked without leaving the page. It is the same assistant as Insights › Assistant
 * (same conversation for this tab, D-095; read-only, D-089). It is not modal: the page stays usable,
 * and a customer or invoice named in an answer opens in the page while the conversation stays here.
 */
export function AssistantButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const { t } = useTranslation();
  return (
    <button aria-controls="assistant-drawer" aria-expanded={open} className="assistant-button" onClick={onToggle} type="button">
      <Icon name="chat" small />
      <span className="assistant-button-label">{t("copilot.open")}</span>
    </button>
  );
}

export function AssistantDrawer({ tenantId, onClose }: { tenantId: string; onClose: () => void }) {
  const { t } = useTranslation();
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    panel.current?.querySelector<HTMLElement>("textarea, input")?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside aria-label={t("copilot.title")} className="assistant-drawer" id="assistant-drawer" ref={panel}>
      <div className="assistant-drawer-head">
        <strong><Icon name="chat" small />{t("copilot.title")}</strong>
        <button aria-label={t("copilot.close")} className="text-btn" onClick={onClose} type="button"><Icon name="close" /></button>
      </div>
      <div className="assistant-drawer-body">
        <CopilotPanel key={tenantId} tenantId={tenantId} />
      </div>
    </aside>
  );
}
