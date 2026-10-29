import { useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import "../../listKit.css";
import { Icon } from "../Icon";
import { ActionMenu, type ListAction } from "./ActionMenu";

type FabTarget =
  | { href: string; onSelect?: never; menu?: never }
  | { onSelect: () => void; href?: never; menu?: never }
  | { menu: readonly ListAction[]; href?: never; onSelect?: never };

/**
 * The floating round "+" of a list page, kept above the phone's bottom bar and keyboard, at the end
 * of the line (bottom-right in English, bottom-left in Arabic). `label` is its accessible name and
 * its visible tooltip. With `menu` it opens a short list of labelled actions instead.
 */
export function Fab({ label, ...target }: { label: string } & FabTarget) {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const face = <><Icon name="plus" /><span aria-hidden="true" className="fab-tip">{label}</span></>;

  if (target.href !== undefined) return <div className="fab-dock"><Link aria-label={label} className="fab" to={target.href}>{face}</Link></div>;
  if (target.onSelect) return <div className="fab-dock"><button aria-label={label} className="fab" onClick={target.onSelect} type="button">{face}</button></div>;
  return (
    <div className="fab-dock">
      {open && target.menu ? <ActionMenu actions={target.menu} className="fab-menu" id={menuId} label={label} onClose={() => setOpen(false)} trigger={button} /> : null}
      <button
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        aria-label={label}
        className="fab"
        onClick={() => setOpen((isOpen) => !isOpen)}
        ref={button}
        type="button"
      >
        {face}
      </button>
    </div>
  );
}
