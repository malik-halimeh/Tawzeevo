import type { SVGProps } from "react";

/** Daylight line icons for the storefront: local SVG geometry, decorative and hidden from assistive technology. */
const PATHS = {
  bag: <path d="M5 7h14l2 14H3ZM8 8V6a4 4 0 0 1 8 0v2" />,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  check: <path d="m5 12 4 4L19 6" />,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  back: <path d="M19 12H5m6-6-6 6 6 6" />,
  search: <><circle cx="10" cy="10" r="6.5" /><path d="m15 15 6 6" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.1" /></>,
  shop: <path d="M4 10v11h16V10M3 3h18l1 7a3 3 0 0 1-5 1 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-5-1Zm6 18v-6h6v6" />,
  lock: <><rect height="11" rx="2" width="14" x="5" y="10" /><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3" /></>,
  phone: <path d="m6 3 4 4-3 3c2 4 3 5 7 7l3-3 4 4-3 3C10 20 4 14 3 6Z" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, small = false, className = "", ...rest }: { name: IconName; small?: boolean } & SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" className={`icon${small ? " icon-small" : ""}${className ? ` ${className}` : ""}`} focusable="false" viewBox="0 0 24 24" {...rest}>
      {PATHS[name]}
    </svg>
  );
}

/** Arrows mirror in right-to-left layouts; product photos, phone numbers and amounts never do. */
export function Arrow({ back = false, small = false }: { back?: boolean; small?: boolean }) {
  return <span className="directional"><Icon name={back ? "back" : "arrow"} small={small} /></span>;
}
