import type { Stop } from "./api";
import { routeBounds, stopsGeoJSON } from "./geo";

it("routeBounds", () => {
  const route: [number, number][] = [
    [-100, 40],
    [-98, 41],
    [-96, 39],
  ];
  expect(routeBounds(route)).toEqual([
    [-100, 39],
    [-96, 41],
  ]);
});

it("stopsGeoJSON numbers stops from 1 in order", () => {
  const stop = (name: string, lng: number) => ({ name, lat: 40, lng }) as Stop;
  const fc = stopsGeoJSON([stop("A", -99), stop("B", -97)]);
  expect(fc.features.map((f) => f.properties)).toEqual([
    { n: 1, label: "A" },
    { n: 2, label: "B" },
  ]);
  expect(fc.features[1].geometry).toEqual({ type: "Point", coordinates: [-97, 40] });
});
