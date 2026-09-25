import type { SVGProps } from "react";

/**
 * Daylight line-icon family (docs/design-references/DESIGN_DIRECTION.md). Every icon is local
 * inline SVG geometry drawn with the same 1.7px stroke; there is no icon library. Icons are
 * decorative by default and hidden from assistive technology — a control that shows only an icon
 * must carry its own accessible name (aria-label or visually hidden text).
 */
const PATHS = {
  work: <><rect height="16" rx="3" width="16" x="4" y="5" /><path d="M8 3v4m8-4v4M4 10h16m-11 5 2 2 4-4" /></>,
  people: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5" /></>,
  person: <><circle cx="12" cy="7" r="4" /><path d="M4 22v-3a8 8 0 0 1 16 0v3" /></>,
  invoice: <path d="M6 3h9l4 4v14H5V3h1m9 0v5h4M8 12h8m-8 4h5" />,
  more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  back: <path d="M19 12H5m6-6-6 6 6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  check: <path d="m5 12 4 4L19 6" />,
  pin: <><path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  phone: <path d="m6 3 4 4-3 3c2 4 3 5 7 7l3-3 4 4-3 3C10 20 4 14 3 6Z" />,
  box: <path d="m12 3 9 5v9l-9 5-9-5V8Zm-9 5 9 5 9-5m-9 5v9M7 5.8l10 5.4" />,
  sync: <path d="M20 7V3l-3 3a8 8 0 0 0-13 6m0 5v4l3-3a8 8 0 0 0 13-6M4 21h4M20 3h-4" />,
  search: <><circle cx="10" cy="10" r="6.5" /><path d="m15 15 6 6" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  coin: <><circle cx="12" cy="12" r="9" /><path d="M15 8h-4a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4H9m3-10v12" /></>,
  shop: <path d="M4 10v11h16V10M3 3h18l1 7a3 3 0 0 1-5 1 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-5-1Zm6 18v-6h6v6" />,
  bag: <path d="M5 7h14l2 14H3ZM8 8V6a4 4 0 0 1 8 0v2" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.1" /></>,
  shield: <path d="m12 3 8 3v6c0 5-8 10-8 10S4 17 4 12V6Zm-4 9 3 3 5-6" />,
  edit: <path d="m15 4 5 5-11 11-6 1 1-6Zm-9 10 5 5m3-14 5 5" />,
  van: <><path d="M2 6h12v11H2Zm12 4h4l4 4v3h-8M17 10v4h5" /><circle cx="6" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>,
  email: <><rect height="14" rx="2" width="18" x="3" y="5" /><path d="m3 6 9 7 9-7" /></>,
  lock: <><rect height="11" rx="2" width="14" x="5" y="10" /><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2" /></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  eyeOff: <><path d="M3 3l18 18M10.6 5.3A11 11 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.6 6.6C3.6 8.6 2 12 2 12s4 7 10 7c1.4 0 2.7-.3 3.8-.8" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></>,
  chart: <path d="M4 20V10m6 10V4m6 16v-7m6 7H2" />,
  logout: <path d="M10 4H5v16h5m4-4 4-4-4-4m4 4H9" />,
  leaf: <path d="M20 3c1 10-2 15-9 15a6 6 0 0 1-6-6c0-7 8-5 15-9ZM3 21 15 9" />,
  building: <path d="M4 21V5l8-2v18M12 21V11l8-2v12M4 21h16M7 9h2m-2 4h2m-2 4h2m8-4h2m-2 4h2" />,
  cloud: <path d="M7 18a4 4 0 0 1-.6-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1 0 9Zm5-6v8m-3-3 3 3 3-3" />,
  layers: <path d="m12 3 9 5-9 5-9-5Zm-9 9 9 5 9-5m-18 4 9 5 9-5" />,
  cart: <><path d="M3 4h2l2.5 11h11L21 7H7" /><circle cx="9" cy="19" r="1.5" /><circle cx="17" cy="19" r="1.5" /></>,
  truck: <><path d="M2 6h12v11H2Zm12 4h4l4 4v3h-8M17 10v4h5" /><circle cx="6" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>,
  scan: <path d="M4 8V4h4m8 0h4v4m0 8v4h-4M8 20H4v-4M8 8v8m4-8v8m4-8v8" />,
  palette: <path d="M12 3a9 9 0 0 0 0 18h1a2 2 0 0 0 1-3.7 2 2 0 0 1 1.5-3.3H17a4 4 0 0 0 4-4c0-4-4-7-9-7Zm-4 7a1 1 0 1 0 0 .1M12 7a1 1 0 1 0 0 .1m4 2a1 1 0 1 0 0 .1" />,
  home: <path d="m3 11 9-8 9 8v10h-6v-6h-6v6H3Z" />,
  key: <path d="M14 10a4 4 0 1 0-4 4l1-1 1 1 2-2 2 2 2-2-4-4 1-1a4 4 0 0 0-1 3Z" />,
  chat: <path d="M5 18.5V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H9l-4 3.5ZM9 8.5h6M9 11.5h4" />,
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, small = false, className = "", ...rest }: { name: IconName; small?: boolean } & SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" className={`icon${small ? " icon-small" : ""}${className ? ` ${className}` : ""}`} focusable="false" viewBox="0 0 24 24" {...rest}>
      {PATHS[name]}
    </svg>
  );
}

/** A directional arrow that mirrors in right-to-left layouts (product photos and numbers never do). */
export function Arrow({ back = false, small = false }: { back?: boolean; small?: boolean }) {
  return <span className="directional"><Icon name={back ? "back" : "arrow"} small={small} /></span>;
}
