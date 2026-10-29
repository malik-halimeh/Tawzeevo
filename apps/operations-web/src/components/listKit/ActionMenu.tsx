import { type KeyboardEvent, type ReactNode, type RefObject, useRef } from "react";
import { Link } from "react-router-dom";

import "../../listKit.css";
import { Icon, type IconName } from "../Icon";
import { ConfirmAction } from "../Ui";
import { moveFocusWithArrows, usePopover } from "./popover";

/**
 * One entry of a small action menu: a link (`href`) or a button (`onSelect`). A `danger` action asks
 * once through ConfirmAction before `onSelect` runs.
 */
export type ListAction =
  | { label: string; icon?: IconName; href: string }
  | { label: string; icon?: IconName; onSelect: () => void; danger?: false }
  | { label: string; icon?: IconName; onSelect: () => void; danger: true; confirmLabel: string; confirmNote?: ReactNode };

/**
 * The open panel of an action menu (a list of labelled controls, not an ARIA menu, so a danger
 * action can show its inline confirmation). Escape closes it and returns focus to the trigger;
 * arrows move between entries; choosing an entry closes it.
 */
export function ActionMenu({ id, label, actions, trigger, onClose, className = "" }: {
  id: string;
  label: string;
  actions: readonly ListAction[];
  trigger: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  className?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  usePopover({ open: true, onDismiss: onClose, trigger, panel });

  function done() {
    onClose();
    trigger.current?.focus();
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (moveFocusWithArrows(event, panel.current)) return;
    if (event.key === "Escape") { event.preventDefault(); done(); }
  }

  return (
    <div aria-label={label} className={`list-menu${className ? ` ${className}` : ""}`} id={id} onKeyDown={onKey} ref={panel} role="group">
      <ul>
        {actions.map((action) => {
          const icon = action.icon ? <Icon name={action.icon} small /> : null;
          if ("href" in action) {
            return <li key={action.label}><Link className="list-menu-item" onClick={onClose} to={action.href}>{icon}{action.label}</Link></li>;
          }
          if (action.danger) {
            return (
              <li key={action.label}>
                <ConfirmAction className="list-menu-item list-menu-danger" confirmLabel={action.confirmLabel} danger icon={icon} label={action.label} onConfirm={() => { action.onSelect(); done(); }}>
                  {action.confirmNote}
                </ConfirmAction>
              </li>
            );
          }
          return <li key={action.label}><button className="list-menu-item" onClick={() => { action.onSelect(); done(); }} type="button">{icon}{action.label}</button></li>;
        })}
      </ul>
    </div>
  );
}
