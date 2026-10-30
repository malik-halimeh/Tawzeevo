import type { ReactNode } from "react";

/** Local 24px geometry: solid silhouettes, transparent details, and rounded open marks. */
export type IconGeometry = { body?: ReactNode; cutout?: ReactNode; strokes?: ReactNode };

// These two names already shared the same delivery silhouette.
const delivery: IconGeometry = {
  body: <><rect x="2" y="6" width="12" height="11" rx="1.5" /><path d="M14 10h3.6q.6 0 1 .4l3 3q.4.4.4 1V17h-8Z" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="18" r="2.5" /></>,
  cutout: <><path d="M14 8v7M3 16h18" /><path d="M16.5 11h1l3 3h-4Z" fill="#000" stroke="none" /></>,
};

export const PATHS = {
  work: {
    body: <><rect height="16" rx="3" width="16" x="4" y="5" /><rect x="7" y="2" width="2.4" height="6" rx="1.2" /><rect x="14.6" y="2" width="2.4" height="6" rx="1.2" /></>,
    cutout: <path d="M4 10h16m-11 5 2 2 4-4" />,
  },
  people: {
    body: <><circle cx="9" cy="7.5" r="3.5" /><path d="M3 21v-3a6 6 0 0 1 12 0v3q0 1-1 1H4q-1 0-1-1ZM16 4a3.5 3.5 0 0 1 0 7ZM17 13a5 5 0 0 1 5 5v3q0 1-1 1h-4Z" /></>,
  },
  person: { body: <><circle cx="12" cy="7" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2q0 1-1 1H5q-1 0-1-1Z" /></> },
  invoice: {
    body: <path d="M6 3h9l4 4v13q0 1-1 1H6q-1 0-1-1V4q0-1 1-1Z" />,
    cutout: <path d="M15 3v5h4M8 12h8m-8 4h5" />,
  },
  more: { strokes: <path d="M5 12h0m7 0h0m7 0h0" /> },
  arrow: { strokes: <path d="M5 12h14m-6-6 6 6-6 6" /> },
  back: { strokes: <path d="M19 12H5m6-6-6 6 6 6" /> },
  plus: { strokes: <path d="M12 5v14M5 12h14" /> },
  minus: { strokes: <path d="M5 12h14" /> },
  check: { strokes: <path d="m5 12 4 4L19 6" /> },
  pin: {
    body: <path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z" />,
    cutout: <circle cx="12" cy="10" r="2.6" fill="#000" stroke="none" />,
  },
  phone: { body: <path d="m6 3 4 4-3 3c2 4 3 5 7 7l3-3 4 4-3 3C10 20 4 14 3 6Z" /> },
  box: {
    body: <path d="m12 3 9 5v9l-9 5-9-5V8Z" />,
    cutout: <path d="m3 8 9 5 9-5m-9 5v9M7 5.8l10 5.4" />,
  },
  sync: { strokes: <path d="M20 7V3l-3 3a8 8 0 0 0-13 6m0 5v4l3-3a8 8 0 0 0 13-6M4 21h4M20 3h-4" /> },
  search: {
    body: <circle cx="10" cy="10" r="7.5" />,
    cutout: <circle cx="10" cy="10" r="4.8" fill="#000" stroke="none" />,
    strokes: <path d="m15.5 15.5 5.5 5.5" />,
  },
  close: { strokes: <path d="m6 6 12 12M6 18 18 6" /> },
  coin: {
    body: <circle cx="12" cy="12" r="9" />,
    cutout: <path d="M15 8h-4a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4H9m3-10v12" />,
  },
  shop: {
    body: <><path d="M4 9h16v11q0 1-1 1H5q-1 0-1-1Z" /><path d="M3 3h18l1 7a3 3 0 0 1-5 1 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-5-1Z" /></>,
    cutout: <><path d="M4 13h16M7 4v5m5-5v5m5-5v5" /><path d="M9 15h6v7H9Z" fill="#000" stroke="none" /></>,
  },
  bag: {
    body: <path d="M5 7h14l2 13q.2 1-1 1H4q-1.2 0-1-1Z" />,
    strokes: <path d="M8 8V6a4 4 0 0 1 8 0v2" />,
  },
  clock: { body: <circle cx="12" cy="12" r="9" />, cutout: <path d="M12 7v5l3 2" /> },
  info: {
    body: <circle cx="12" cy="12" r="9" />,
    cutout: <><path d="M12 11v6" /><circle cx="12" cy="7.5" r="1.1" fill="#000" stroke="none" /></>,
  },
  shield: {
    body: <path d="m12 3 8 3v6c0 5-8 10-8 10S4 17 4 12V6Z" />,
    cutout: <path d="m8 12 3 3 5-6" />,
  },
  edit: {
    body: <path d="m15 4 5 5-11 11-6 1 1-6Z" />,
    cutout: <path d="m6 14 5 5m3-14 5 5" />,
  },
  van: delivery,
  email: {
    body: <rect height="14" rx="2" width="18" x="3" y="5" />,
    cutout: <path d="m3 6 9 7 9-7" />,
  },
  lock: {
    body: <rect height="11" rx="2" width="14" x="5" y="10" />,
    cutout: <><circle cx="12" cy="14" r="1.4" fill="#000" stroke="none" /><path d="M12 14v3" /></>,
    strokes: <path d="M8 10V6a4 4 0 0 1 8 0v4" />,
  },
  sun: {
    body: <circle cx="12" cy="12" r="4.5" />,
    strokes: <path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.5 4.5 6 6m12 12 1.5 1.5m-15 0L6 18M18 6l1.5-1.5" />,
  },
  eye: {
    body: <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />,
    cutout: <circle cx="12" cy="12" r="3.2" strokeWidth="2" />,
  },
  eyeOff: {
    body: <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />,
    cutout: <><circle cx="12" cy="12" r="3.2" strokeWidth="2" /><path d="M3 3l18 18" strokeWidth="4.8" /></>,
    strokes: <path d="M3 3l18 18" />,
  },
  chart: { strokes: <path d="M4 20V10m6 10V4m6 16v-7m6 7H2" /> },
  logout: { strokes: <path d="M10 4H5v16h5m4-4 4-4-4-4m4 4H9" /> },
  leaf: {
    body: <path d="M20 3c1 10-2 15-9 15a6 6 0 0 1-6-6c0-7 8-5 15-9Z" />,
    cutout: <path d="m6 18 9-9" />,
    strokes: <path d="m3 21 3-3" />,
  },
  building: {
    body: <path d="M4 21V5l8-2v8l8-2v12Z" />,
    cutout: <path d="M12 11v10M7 9h2m-2 4h2m-2 4h2m7-4h2m-2 4h2" />,
  },
  cloud: {
    body: <path d="M7 18a4 4 0 0 1-.6-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1 0 9Z" />,
    cutout: <path d="M12 10v6m-3-3 3 3 3-3" />,
  },
  layers: {
    body: <path d="m12 3 9 5-9 5-9-5Z" />,
    strokes: <path d="m3 12 9 5 9-5m-18 4 9 5 9-5" />,
  },
  cart: {
    body: <><path d="M6 7h15l-2.5 8h-11Z" /><circle cx="9" cy="19" r="2" /><circle cx="17" cy="19" r="2" /></>,
    strokes: <path d="M3 4h2l2.5 11h11" />,
  },
  truck: delivery,
  scan: { strokes: <path d="M4 8V4h4m8 0h4v4m0 8v4h-4M8 20H4v-4M8 8v8m4-8v8m4-8v8" /> },
  palette: {
    body: <path d="M12 3a9 9 0 0 0 0 18h1a2 2 0 0 0 1-3.7 2 2 0 0 1 1.5-3.3H17a4 4 0 0 0 4-4c0-4-4-7-9-7Z" />,
    cutout: <><circle cx="7.5" cy="10" r="1.3" fill="#000" stroke="none" /><circle cx="12" cy="7" r="1.3" fill="#000" stroke="none" /><circle cx="16.5" cy="9" r="1.3" fill="#000" stroke="none" /></>,
  },
  home: { body: <path d="m3 11 9-8 9 8v9q0 1-1 1h-5v-6H9v6H4q-1 0-1-1Z" /> },
  key: {
    body: <><circle cx="9" cy="9" r="5" /><path d="m12 10 8 8-2 2-2-2-2 1-1-2-3-3Z" /></>,
    cutout: <circle cx="8" cy="8" r="1.6" fill="#000" stroke="none" />,
  },
  chat: {
    body: <path d="M5 18.5V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H9Z" />,
    cutout: <path d="M9 8.5h6M9 11.5h4" />,
  },
} as const satisfies Record<string, IconGeometry>;
