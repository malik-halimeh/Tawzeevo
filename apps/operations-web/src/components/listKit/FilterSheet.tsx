import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import "../../listKit.css";
import { Icon } from "../Icon";
import { focusables } from "./popover";

/**
 * A "Filters" button (with the number of filters in use) that opens the filter fields as a bottom
 * sheet on a phone and a side panel on wider screens. Focus stays inside while it is open; Escape,
 * Close and the backdrop close it and focus returns to the button. "Clear" calls `onClear` and keeps
 * the sheet open; "Apply" calls `onApply` and closes it. The fields themselves are the children.
 */
export function FilterSheet({ activeCount, onApply, onClear, onClose, title, children }: {
  activeCount: number;
  onApply: () => void;
  onClear: () => void;
  /** Called when the sheet closes without Apply, e.g. to drop unapplied changes. */
  onClose?: () => void;
  title?: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const heading = title ?? t("listKit.filters");

  useEffect(() => {
    if (!open) return;
    const body = dialog.current?.querySelector<HTMLElement>(".filter-sheet-body");
    (focusables(body ?? null)[0] ?? closeButton.current)?.focus();
  }, [open]);

  function close(applied: boolean) {
    setOpen(false);
    if (!applied) onClose?.();
    opener.current?.focus();
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.preventDefault(); close(false); return; }
    if (event.key !== "Tab") return;
    const items = focusables(dialog.current);
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  return (
    <>
      <button aria-expanded={open} aria-haspopup="dialog" className="filter-sheet-button" onClick={() => setOpen(true)} ref={opener} type="button">
        {heading}
        {activeCount > 0 ? (
          <>
            {" "}<bdi aria-hidden="true" className="chip-count" dir="ltr">{activeCount}</bdi>
            <span className="sr-only">{t("listKit.activeFilters", { count: activeCount })}</span>
          </>
        ) : null}
      </button>
      {open ? (
        <>
          <div aria-hidden="true" className="filter-sheet-backdrop" onClick={() => close(false)} />
          <div aria-labelledby={titleId} aria-modal="true" className="filter-sheet" onKeyDown={onKey} ref={dialog} role="dialog">
            <div className="filter-sheet-head">
              <h2 id={titleId}>{heading}</h2>
              <button aria-label={t("common.close")} className="list-icon-button" onClick={() => close(false)} ref={closeButton} type="button"><Icon name="close" /></button>
            </div>
            <div className="filter-sheet-body">{children}</div>
            <div className="filter-sheet-foot">
              <button className="button button-secondary" onClick={onClear} type="button">{t("common.clear")}</button>
              <button className="button" onClick={() => { onApply(); close(true); }} type="button">{t("common.apply")}</button>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
