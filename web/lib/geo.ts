import type { Stop } from "./api";

type LngLat = [number, number];

export function routeBounds(coords: LngLat[]): [LngLat, LngLat] {
  const lngs = coords.map((c) => c[0]);
  const lats = coords.map((c) => c[1]);
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}

export function stopsGeoJSON(stops: Stop[]) {
  return {
    type: "FeatureCollection" as const,
    features: stops.map((s, i) => ({
      type: "Feature" as const,
      properties: { n: i + 1, label: s.name },
      geometry: { type: "Point" as const, coordinates: [s.lng, s.lat] as LngLat },
    })),
  };
}
