import { render } from "@testing-library/react";
import maplibregl from "maplibre-gl";

import type { PlanDocument } from "@/lib/api";
import fixture from "@/test/fixtures/austin-chicago.json";

import RouteMap from "./RouteMap";

jest.mock("maplibre-gl", () => {
  const map = {
    on: jest.fn((event: string, cb: () => void) => event === "load" && cb()),
    addSource: jest.fn(),
    addLayer: jest.fn(),
    addControl: jest.fn(),
    fitBounds: jest.fn(),
    remove: jest.fn(),
  };
  class Marker {
    setLngLat() {
      return this;
    }
    addTo() {
      return this;
    }
  }
  return {
    __esModule: true,
    default: { Map: jest.fn(() => map), Marker, AttributionControl: jest.fn() },
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
