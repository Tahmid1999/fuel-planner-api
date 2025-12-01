from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import folium
import requests
from geopy.geocoders import Nominatim
from pyproj import Transformer
from shapely.geometry import LineString, Point

BASE_DIR = Path(__file__).resolve().parents[1]
STATIONS_DATA_PATH = BASE_DIR / "data" / "stations_with_coords.json"

MILES_TO_METERS = 1609.34
ROUTE_BUFFER_MILES = 30
START_SEARCH_MILES = 250

GEOCODER = Nominatim(user_agent="fuelplanner-app", timeout=10)
TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


class PlannerError(Exception):
    pass


@dataclass
class Location:
    label: str
    latitude: float
    longitude: float

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass(frozen=True)
class Station:
    opis_id: str
    name: str
    city: str
    state: str
    price: float
    latitude: float
    longitude: float
    projected_point: Point

    def to_dict(self) -> dict:
        return {
            "opis_id": self.opis_id,
            "name": self.name,
            "city": self.city,
            "state": self.state,
            "price_per_gallon": round(self.price, 3),
            "coordinates": {"latitude": self.latitude, "longitude": self.longitude},
        }


@dataclass
class Route:
    coordinates: List[Tuple[float, float]]
    distance_miles: float
    duration_minutes: float
    line_wgs84: LineString
    line_projected: LineString


@dataclass
class RouteStation:
    station: Station
    mile_marker: float
    distance_from_route_miles: float


@dataclass
class FuelStop:
    station: Station
    mile_marker: float
    distance_from_route_miles: float
    stop_type: str

    def serialize(self) -> dict:
        payload = self.station.to_dict()
        payload.update(
            {
                "mile_marker": round(self.mile_marker, 2),
                "distance_from_route_miles": round(self.distance_from_route_miles, 2),
                "type": self.stop_type,
            }
        )
        return payload


def miles_to_meters(miles: float) -> float:
    return miles * MILES_TO_METERS


def meters_to_miles(meters: float) -> float:
    return meters / MILES_TO_METERS


def plan_route(
    start: str,
    finish: str,
    vehicle_range_miles: float,
    fuel_efficiency_mpg: float,
) -> dict:
    start_loc = geocode_location(start)
    finish_loc = geocode_location(finish)
    route = fetch_route(start_loc, finish_loc)

    stations = list(_station_catalog_cache())
    start_station = find_nearest_station(start_loc, stations)
    route_stations = list(stations_near_route(route, stations))
    fuel_plan = build_fuel_plan(
        route=route,
        start_location=start_loc,
        start_station=start_station,
        route_stations=route_stations,
        vehicle_range_miles=vehicle_range_miles,
        fuel_efficiency_mpg=fuel_efficiency_mpg,
    )
    map_html = render_map(route, start_loc, finish_loc, fuel_plan["stops"])

    return {
        "start": start_loc.to_dict(),
        "finish": finish_loc.to_dict(),
        "vehicle": {
            "range_miles": vehicle_range_miles,
            "fuel_efficiency_mpg": fuel_efficiency_mpg,
        },
        "route": {
            "distance_miles": round(route.distance_miles, 2),
            "duration_minutes": round(route.duration_minutes, 1),
        },
        "fuel_plan": fuel_plan,
        "map_html": map_html,
    }


def geocode_location(query: str) -> Location:
    result = GEOCODER.geocode(
        query,
        exactly_one=True,
        country_codes="us",
        addressdetails=False,
        language="en",
    )
    if result is None:
        raise PlannerError(f"Unable to geocode '{query}'. Please provide a U.S. location.")

    return Location(label=result.address, latitude=result.latitude, longitude=result.longitude)


def fetch_route(start: Location, finish: Location) -> Route:
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{start.longitude},{start.latitude};{finish.longitude},{finish.latitude}"
    )
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}
    response = requests.get(url, params=params, timeout=20)
    if response.status_code != 200:
        raise PlannerError("Failed to fetch route from OSRM.")
    data = response.json()
    if data.get("code") != "Ok":
        raise PlannerError(data.get("message", "Routing service returned an error."))

    route_info = data["routes"][0]
    coordinates = route_info["geometry"]["coordinates"]
    line_wgs84 = LineString(coordinates)
    projected_coords = [TRANSFORMER.transform(lon, lat) for lon, lat in coordinates]
    line_projected = LineString(projected_coords)
    distance_miles = meters_to_miles(route_info["distance"])
    duration_minutes = route_info["duration"] / 60

    return Route(
        coordinates=coordinates,
        distance_miles=distance_miles,
        duration_minutes=duration_minutes,
        line_wgs84=line_wgs84,
        line_projected=line_projected,
    )


def load_station_catalog() -> List[Station]:
    if not STATIONS_DATA_PATH.exists():
        raise PlannerError(
            "Station dataset not found. Run scripts/build_station_dataset.py first."
        )

    with STATIONS_DATA_PATH.open(encoding="utf-8") as handle:
        raw_records = json.load(handle)

    stations = []
    for entry in raw_records:
        lon = entry["longitude"]
        lat = entry["latitude"]
        x, y = TRANSFORMER.transform(lon, lat)
        stations.append(
            Station(
                opis_id=entry["opis_id"],
                name=entry["name"],
                city=entry["city"],
                state=entry["state"],
                price=float(entry["retail_price"]),
                latitude=lat,
                longitude=lon,
                projected_point=Point(x, y),
            )
        )
    return stations


@lru_cache(maxsize=1)
def _station_catalog_cache() -> Tuple[Station, ...]:
    return tuple(load_station_catalog())


def find_nearest_station(location: Location, stations: Sequence[Station]) -> Station:
    origin_x, origin_y = TRANSFORMER.transform(location.longitude, location.latitude)
    origin_point = Point(origin_x, origin_y)

    best_station = None
    best_distance = float("inf")
    for station in stations:
        distance_miles = meters_to_miles(origin_point.distance(station.projected_point))
        if distance_miles < best_distance:
            best_distance = distance_miles
            best_station = station

    if best_station is None or best_distance > START_SEARCH_MILES:
        raise PlannerError(
            "No nearby fuel stations found near the start location. "
            "Try entering a larger nearby city."
        )

    return best_station


def stations_near_route(route: Route, stations: Sequence[Station]) -> Iterable[RouteStation]:
    threshold = miles_to_meters(ROUTE_BUFFER_MILES)
    route_length = route.line_projected.length

    for station in stations:
        distance_to_route = route.line_projected.distance(station.projected_point)
        if distance_to_route > threshold:
            continue

        along_route = route.line_projected.project(station.projected_point)
        if along_route < 0 or along_route > route_length:
            continue

        yield RouteStation(
            station=station,
            mile_marker=meters_to_miles(along_route),
            distance_from_route_miles=meters_to_miles(distance_to_route),
        )


def build_fuel_plan(
    route: Route,
    start_location: Location,
    start_station: Station,
    route_stations: Sequence[RouteStation],
    vehicle_range_miles: float,
    fuel_efficiency_mpg: float,
) -> dict:
    start_point = Point(*TRANSFORMER.transform(start_location.longitude, start_location.latitude))
    start_distance = meters_to_miles(start_point.distance(start_station.projected_point))
    start_stop = FuelStop(
        station=start_station,
        mile_marker=0.0,
        distance_from_route_miles=start_distance,
        stop_type="start",
    )
    sorted_candidates = sorted(route_stations, key=lambda entry: entry.mile_marker)
    selected_route_stations = select_route_stops(
        route=route,
        candidates=sorted_candidates,
        vehicle_range_miles=vehicle_range_miles,
    )
    mid_route_stops = [
        FuelStop(
            station=entry.station,
            mile_marker=entry.mile_marker,
            distance_from_route_miles=entry.distance_from_route_miles,
            stop_type="mid_route",
        )
        for entry in selected_route_stations
    ]
    ordered_stops = [start_stop] + mid_route_stops
    total_cost, total_gallons, segments = calculate_costs(
        ordered_stops, route.distance_miles, fuel_efficiency_mpg
    )

    return {
        "stops": [stop.serialize() for stop in ordered_stops],
        "segments": segments,
        "total_gallons": round(total_gallons, 2),
        "total_cost_usd": round(total_cost, 2),
    }


def select_route_stops(
    route: Route,
    candidates: Sequence[RouteStation],
    vehicle_range_miles: float,
) -> List[RouteStation]:

    if route.distance_miles <= vehicle_range_miles:
        return []

    selected: List[RouteStation] = []
    remaining = list(candidates)
    current_position = 0.0

    while current_position + vehicle_range_miles < route.distance_miles:
        reachable = current_position + vehicle_range_miles
        window = [c for c in remaining if current_position < c.mile_marker <= reachable]
        if not window:
            raise PlannerError(
                "Route contains a stretch without affordable fuel stops. "
                "Try adjusting start/end points."
            )

        best_option = min(window, key=lambda candidate: candidate.station.price)
        selected.append(best_option)
        current_position = best_option.mile_marker
        remaining = [c for c in remaining if c.mile_marker > current_position]

    return selected


def calculate_costs(
    stops: Sequence[FuelStop],
    route_distance_miles: float,
    fuel_efficiency_mpg: float,
) -> Tuple[float, float, List[dict]]:
    segments = []
    total_cost = 0.0
    total_gallons = 0.0

    end_markers = [stop.mile_marker for stop in stops[1:]] + [route_distance_miles]
    for stop, end_marker in zip(stops, end_markers):
        segment_distance = max(end_marker - stop.mile_marker, 0)
        if segment_distance <= 0:
            continue

        gallons = segment_distance / fuel_efficiency_mpg
        cost = gallons * stop.station.price
        total_cost += cost
        total_gallons += gallons
        segments.append(
            {
                "from_stop": stop.station.name,
                "segment_distance_miles": round(segment_distance, 2),
                "gallons_used": round(gallons, 2),
                "price_per_gallon": round(stop.station.price, 3),
                "cost_usd": round(cost, 2),
            }
        )

    return total_cost, total_gallons, segments


def render_map(
    route: Route,
    start: Location,
    finish: Location,
    stop_payloads: Sequence[dict],
) -> str:
    if not route.coordinates:
        raise PlannerError("No geometry available for the requested route.")

    first_coord = route.coordinates[0]
    map_center = [first_coord[1], first_coord[0]]
    fmap = folium.Map(location=map_center, zoom_start=5)
    folium.PolyLine([[lat, lon] for lon, lat in route.coordinates], color="blue", weight=4).add_to(fmap)

    folium.Marker([start.latitude, start.longitude], popup="Start", icon=folium.Icon(color="green")).add_to(fmap)
    folium.Marker([finish.latitude, finish.longitude], popup="Finish", icon=folium.Icon(color="red")).add_to(fmap)

    for stop in stop_payloads:
        coords = stop["coordinates"]
        label = f"{stop['name']} (${stop['price_per_gallon']}/gal)"
        folium.CircleMarker(
            location=[coords["latitude"], coords["longitude"]],
            radius=6,
            color="orange" if stop["type"] == "mid_route" else "purple",
            fill=True,
            fill_color="orange" if stop["type"] == "mid_route" else "purple",
            popup=label,
        ).add_to(fmap)

    return fmap.get_root().render()


def list_available_cities() -> List[str]:
    stations = _station_catalog_cache()
    unique = {f"{station.city}, {station.state}" for station in stations}
    return sorted(unique)

