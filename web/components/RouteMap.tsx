"use client";

import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";

import type { Place, Stop } from "@/lib/api";
import { endsGeoJSON, routeBounds, stopsGeoJSON } from "@/lib/geo";

// Free, no key, no request limit; it asks for the credit line below.
const STYLE = "https://tiles.openfreemap.org/styles/liberty";
const BLUE = "#1677ff";

type Props = { route: [number, number][]; stops: Stop[]; from: Place; to: Place };

export default function RouteMap({ route, stops, from, to }: Props) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const map = new maplibregl.Map({
      container: box.current!,
      style: STYLE,
      // The credit goes under the map instead: on a phone MapLibre's box
      // opens over the bottom of the map, where the start usually is.
      attributionControl: false,
      cooperativeGestures: true, // one finger scrolls the page on a phone, two move the map
    });
    map.fitBounds(routeBounds(route), { padding: 32, animate: false });

    // "load" waits for every tile; one slow or failed tile would keep the
    // route off the map, so draw as soon as the style is ready.
    map.on("style.load", () => {
      map.addSource("route", {
        type: "geojson",
        data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: route } },
      });
      map.addLayer({
        id: "route",
        type: "line",
        source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": BLUE, "line-width": 4 },
      });
      // A and B are layers rather than HTML markers so they sit under the
      // stops: the first stop is often a few miles from the start.
      map.addSource("ends", { type: "geojson", data: endsGeoJSON(from, to) });
      map.addLayer({
        id: "ends",
        type: "circle",
        source: "ends",
        paint: { "circle-radius": 10, "circle-color": "#262626" },
      });
      map.addLayer({
        id: "end-labels",
        type: "symbol",
        source: "ends",
        layout: {
          "text-field": ["get", "label"],
          "text-font": ["Noto Sans Bold"],
          "text-size": 11,
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#fff" },
      });
      map.addSource("stops", { type: "geojson", data: stopsGeoJSON(stops) });
      map.addLayer({
        id: "stops",
        type: "circle",
        source: "stops",
        paint: {
          "circle-radius": 9,
          "circle-color": "#fff",
          "circle-stroke-color": BLUE,
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "stop-numbers",
        type: "symbol",
        source: "stops",
        layout: {
          "text-field": ["to-string", ["get", "n"]],
          "text-font": ["Noto Sans Bold"],
          "text-size": 11,
          "text-allow-overlap": true,
        },
        paint: { "text-color": BLUE },
      });
    });

    return () => map.remove();
  }, [route, stops, from, to]);

  return (
    <>
      <div ref={box} className="route-map" />
      <div className="map-credit">
        <a href="https://openfreemap.org">OpenFreeMap</a> ©{" "}
        <a href="https://www.openmaptiles.org/">OpenMapTiles</a> Data from{" "}
        <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>
      </div>
    </>
  );
}
