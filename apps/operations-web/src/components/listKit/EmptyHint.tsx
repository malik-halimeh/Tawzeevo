import { Link } from "react-router-dom";

import "../../listKit.css";
import type { IconName } from "../Icon";
import { EmptyState } from "../Ui";

export type EmptyHintAction = { label: string; href: string } | { label: string; onSelect: () => void };

/** A compact EmptyState for a list: an icon, one line and an optional next step. */
export function EmptyHint({ icon, text, action }: { icon?: IconName; text: string; action?: EmptyHintAction }) {
  const next = action
    ? "href" in action
      ? <Link className="button button-small" to={action.href}>{action.label}</Link>
      : <button className="button button-small" onClick={action.onSelect} type="button">{action.label}</button>
    : null;
  return <EmptyState action={next} className="empty-hint" icon={icon} title={text} />;
}
