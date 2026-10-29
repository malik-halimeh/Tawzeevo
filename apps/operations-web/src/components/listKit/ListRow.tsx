import { type ReactNode, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import "../../listKit.css";
import { Icon } from "../Icon";
import { StatusBadge } from "../Ui";
import { ActionMenu, type ListAction } from "./ActionMenu";

type RowTarget = { href: string; onOpen?: never } | { onOpen: () => void; href?: never };

/**
 * One record in a list (an `<li>`: place it in MonthGroup or a `<ul className="list-rows">`). The
 * whole row is one link or button; the ⋮ button beside it opens the row's actions. `amount` is shown
 * left-to-right in both languages; a `subline` holding a phone number should wrap it in
 * `<bdi dir="ltr">` itself. `status` is a status code shown with StatusBadge.
 */
export function ListRow({ title, subline, amount, status, actions = [], ...target }: {
  title: string;
  subline?: ReactNode;
  amount?: ReactNode;
  status?: string | undefined;
  actions?: readonly ListAction[];
} & RowTarget) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const more = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const content = (
    <>
      <span className="list-row-text">
        <span className="list-row-title">{title}</span>
        {subline ? <span className="list-row-sub">{subline}</span> : null}
      </span>
      {amount !== undefined || status ? (
        <span className="list-row-end">
          {amount !== undefined ? <bdi className="list-row-amount" dir="ltr">{amount}</bdi> : null}
          {status ? <StatusBadge value={status} /> : null}
        </span>
      ) : null}
    </>
  );
  const menuLabel = t("listKit.rowActions", { title });

  return (
    <li className="list-row">
      {target.href !== undefined
        ? <Link className="list-row-main" to={target.href}>{content}</Link>
        : <button className="list-row-main" onClick={target.onOpen} type="button">{content}</button>}
      {actions.length ? (
        <div className="list-row-actions">
          <button
            aria-controls={menuOpen ? menuId : undefined}
            aria-expanded={menuOpen}
            aria-label={menuLabel}
            className="list-icon-button list-row-more"
            onClick={() => setMenuOpen((open) => !open)}
            ref={more}
            type="button"
          >
            <Icon name="more" />
          </button>
          {menuOpen ? <ActionMenu actions={actions} id={menuId} label={menuLabel} onClose={() => setMenuOpen(false)} trigger={more} /> : null}
        </div>
      ) : null}
    </li>
  );
}
