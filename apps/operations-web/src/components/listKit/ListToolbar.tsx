import type { ReactNode } from "react";

import "../../listKit.css";

/** One list control row: chips scroll within their column; filters and sort stay reachable. */
export function ListToolbar({ chips, filters, sort }: { chips?: ReactNode; filters?: ReactNode; sort?: ReactNode }) {
  return <div className="list-toolbar">{chips ? <div className="list-toolbar-chips">{chips}</div> : null}{filters}{sort}</div>;
}
