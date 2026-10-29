import { type KeyboardEvent, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import "../../listKit.css";
import { Icon } from "../Icon";
import { moveFocusWithArrows, usePopover } from "./popover";

export type SortOption<T extends string> = { value: T; label: string };

/** The current sort order as a small button ("Newest ▾") opening a single-choice menu. */
export function SortMenu<T extends string>({ value, options, onChange, label }: {
  value: T;
  options: readonly SortOption<T>[];
  onChange: (value: T) => void;
  /** Visually hidden prefix of the button's name; defaults to "Sort by". */
  label?: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const current = options.find((option) => option.value === value);
  const name = label ?? t("listKit.sortBy");
  usePopover({
    open,
    onDismiss: () => setOpen(false),
    trigger,
    panel: menu,
    initialFocus: () => menu.current?.querySelector<HTMLElement>('[aria-checked="true"]'),
  });

  function close() {
    setOpen(false);
    trigger.current?.focus();
  }

  function choose(next: T) {
    close();
    if (next !== value) onChange(next);
  }

  function onMenuKey(event: KeyboardEvent<HTMLDivElement>) {
    if (moveFocusWithArrows(event, menu.current)) return;
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (event.key === "Tab") { setOpen(false); return; }
    if (event.key === "Enter" || event.key === " ") {
      const chosen = (document.activeElement as HTMLElement | null)?.dataset.value;
      const option = options.find((item) => item.value === chosen);
      if (option) { event.preventDefault(); choose(option.value); }
    }
  }

  function onTriggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setOpen(true); }
  }

  return (
    <div className="list-sort">
      <button
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        aria-haspopup="menu"
        className="list-sort-button"
        onClick={() => setOpen((isOpen) => !isOpen)}
        onKeyDown={onTriggerKey}
        ref={trigger}
        type="button"
      >
        <span className="sr-only">{name}</span>{" "}{current?.label}<span aria-hidden="true" className="list-sort-caret">▾</span>
      </button>
      {open ? (
        <div aria-label={name} className="list-menu" id={menuId} onKeyDown={onMenuKey} ref={menu} role="menu">
          {options.map((option) => (
            <button
              aria-checked={option.value === value}
              className="list-menu-item"
              data-value={option.value}
              key={option.value}
              onClick={() => choose(option.value)}
              role="menuitemradio"
              tabIndex={-1}
              type="button"
            >
              <span className="list-menu-check">{option.value === value ? <Icon name="check" small /> : null}</span>{option.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
