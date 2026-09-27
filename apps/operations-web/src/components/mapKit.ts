import L from "leaflet";

/**
 * Shared map pieces (D-092): the tile source and the base map. Map images come from MapTiler with
 * the app's browser key; without a key (local development only) OpenStreetMap's tiles are used.
 */
const MAPTILER_KEY = (import.meta.env.VITE_MAPTILER_API_KEY as string | undefined)?.trim();
export const TILES = MAPTILER_KEY
  ? { url: `https://api.maptiler.com/maps/streets-v2/256/{z}/{x}/{y}.png?key=${MAPTILER_KEY}`, attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank" rel="noreferrer">© MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>' }
  : { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a>' };

const LEBANON: L.LatLngTuple = [33.89, 35.5];

/** A map with the app's tile source, centred on Lebanon until the caller fits it to its content. */
export function createBaseMap(element: HTMLElement): L.Map {
  const created = L.map(element, { scrollWheelZoom: false, zoomSnap: 0.25, zoomControl: true, attributionControl: true }).setView(LEBANON, 9);
  L.tileLayer(TILES.url, { attribution: TILES.attribution, maxZoom: 19 }).addTo(created);
  return created;
}

/** A CSS colour token (`var(--blue)`) as a value SVG attributes accept. */
export function tokenColour(element: Element, token: string, fallback: string): string {
  return getComputedStyle(element).getPropertyValue(token.replace(/^var\((.*)\)$/, "$1")).trim() || fallback;
}
