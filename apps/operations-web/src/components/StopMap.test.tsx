import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { StopMap } from "./StopMap";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const stops = [
  { taskId: "a", number: 1, name: "Hamra Shop", latitude: "33.896600", longitude: "35.482300" },
  { taskId: "b", number: 2, name: "Tyre Shop", latitude: "33.273300", longitude: "35.203600" },
  { taskId: "c", number: 3, name: "Nowhere", latitude: null, longitude: null },
];

test("pins follow the stop order, the line comes from the server, and unlocated stops are counted", async () => {
  await i18n.changeLanguage("en");
  const bodies: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    bodies.push(JSON.parse(typeof init?.body === "string" ? init.body : "null"));
    return Promise.resolve(Response.json({ method: "openrouteservice", points: [[33.8966, 35.4823], [33.5, 35.3], [33.2733, 35.2036]] }));
  }));
  const onSelect = vi.fn();
  const { container } = render(<StopMap onSelect={onSelect} routes={[{ key: "r1", stops }]} selectedId="b" tenantId="map-t1" />);

  expect(screen.getByRole("region", { name: "Map of the stops" })).toBeInTheDocument();
  const pins = [...container.querySelectorAll(".map-pin")];
  expect(pins.map((pin) => pin.textContent)).toEqual(["1", "2"]);
  expect(pins[1]).toHaveClass("selected");
  expect(await screen.findByText(/the line is the road route from OpenRouteService/)).toBeInTheDocument();
  expect(screen.getByText(/1 stop has no saved location and is not on the map/)).toBeInTheDocument();
  expect(bodies).toEqual([{ task_ids: ["a", "b"] }]); // located stops only, in order
  (container.querySelectorAll(".leaflet-marker-icon")[1] as HTMLElement).click();
  expect(onSelect).toHaveBeenCalledWith("b");
});

test("without the provider the stops are joined by straight lines that say so; several routes get a legend", async () => {
  await i18n.changeLanguage("en");
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(Response.json({ method: "straight-line", points: [[33.8966, 35.4823], [33.2733, 35.2036]] }))));
  render(<StopMap routes={[{ key: "r1", label: "Rana", stops: stops.slice(0, 2) }, { key: "r2", label: "Karim", stops: [stops[2]!] }]} tenantId="map-t2" />);
  await waitFor(() => expect(screen.getByText(/straight lines join them, not the road route/)).toBeInTheDocument());
  expect(screen.getByRole("list", { name: "Routes on the map" })).toHaveTextContent("RanaKarim");
});
