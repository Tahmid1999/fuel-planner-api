import { render } from "@testing-library/react";
import maplibregl from "maplibre-gl";

import type { PlanDocument } from "@/lib/api";
import fixture from "@/test/fixtures/austin-chicago.json";

import RouteMap from "./RouteMap";

jest.mock("maplibre-gl", () => {
  const map = {
    // layers go on as soon as the style is ready, not after every tile has loaded
    on: jest.fn((event: string, cb: () => void) => event === "style.load" && cb()),
    addSource: jest.fn(),
    addLayer: jest.fn(),
    addControl: jest.fn(),
    fitBounds: jest.fn(),
    remove: jest.fn(),
  };
  return {
    __esModule: true,
    default: { Map: jest.fn(() => map) },
  };
});

const doc = fixture as unknown as PlanDocument;
const map = () => (maplibregl.Map as unknown as jest.Mock).mock.results[0].value;

function draw() {
  return render(
    <RouteMap
      route={doc.route.geometry.coordinates}
      stops={doc.plan.stops}
      from={doc.from}
      to={doc.to}
    />,
  );
}

beforeEach(() => (maplibregl.Map as unknown as jest.Mock).mockClear());

it("uses the openfreemap style", () => {
  draw();
  const options = (maplibregl.Map as unknown as jest.Mock).mock.calls[0][0];
  expect(options.style).toBe("https://tiles.openfreemap.org/styles/liberty");
});

it("adds the route and stops sources with the given data", () => {
  draw();
  const sources = Object.fromEntries(map().addSource.mock.calls);
  expect(sources.route.data.geometry.coordinates).toBe(doc.route.geometry.coordinates);
  expect(sources.stops.data.features).toHaveLength(3);
  expect(sources.stops.data.features[0].properties).toEqual({ n: 1, label: "PWI #168" });
});

it("draws A and B under the stops, so a stop next to either one stays visible", () => {
  draw();
  const sources = Object.fromEntries(map().addSource.mock.calls);
  const labels = sources.ends.data.features.map((f: { properties: { label: string } }) => f.properties.label);
  expect(labels).toEqual(["A", "B"]);
  const layers = map().addLayer.mock.calls.map(([layer]: [{ id: string }]) => layer.id);
  expect(layers.indexOf("end-labels")).toBeLessThan(layers.indexOf("stops"));
});

it("fits the route bounds", () => {
  draw();
  const [bounds] = map().fitBounds.mock.calls[0];
  const lngs = doc.route.geometry.coordinates.map((c) => c[0]);
  expect(bounds[0][0]).toBe(Math.min(...lngs));
  expect(bounds[1][0]).toBe(Math.max(...lngs));
});

it("removes the map on unmount", () => {
  draw().unmount();
  expect(map().remove).toHaveBeenCalled();
});

it("credits the map data under the map, not over the start pin", () => {
  const { getByRole } = draw();
  expect(getByRole("link", { name: "OpenStreetMap" })).toHaveAttribute(
    "href",
    "https://www.openstreetmap.org/copyright",
  );
  const options = (maplibregl.Map as unknown as jest.Mock).mock.calls[0][0];
  expect(options.attributionControl).toBe(false);
  expect(map().addControl).not.toHaveBeenCalled();
});
