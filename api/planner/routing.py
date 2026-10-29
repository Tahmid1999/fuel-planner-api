from dataclasses import dataclass

import requests
from django.db import IntegrityError, transaction
from shapely import LineString

from .models import RouteCache

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
# The public OSRM server asks for an identifying User-Agent and light use.
USER_AGENT = "fuel-planner (github.com/Tahmid1999/fuel-planner-api)"
MILE_M = 1609.344
# About 50 m; a cross-country route drops from tens of thousands of points to
# a few thousand, which is plenty for the map and the station search.
SIMPLIFY_DEG = 0.0005


@dataclass
class RouteData:
    geometry: list[tuple[float, float]]  # (lng, lat)
    distance_mi: float
    duration_min: float


class RoutingUnavailable(Exception):
    pass


class NoRoute(Exception):
    """OSRM found no road between the two places (Hawaii to Denver)."""


def get_route(from_city, to_city):
    cached = RouteCache.objects.filter(from_city=from_city, to_city=to_city).first()
    if cached:
        return RouteData(
            [tuple(p) for p in cached.geometry], cached.distance_mi, cached.duration_min
        )

    route = _fetch(from_city, to_city)
    try:
        with transaction.atomic():
            RouteCache.objects.create(
                from_city=from_city,
                to_city=to_city,
                geometry=[list(p) for p in route.geometry],
                distance_mi=route.distance_mi,
                duration_min=route.duration_min,
            )
    except IntegrityError:
        # another request for the same pair saved its route first; use that one
        winner = RouteCache.objects.get(from_city=from_city, to_city=to_city)
        return RouteData(
            [tuple(p) for p in winner.geometry], winner.distance_mi, winner.duration_min
        )
    return route


def _fetch(from_city, to_city):
    url = f"{OSRM_URL}{from_city.lng},{from_city.lat};{to_city.lng},{to_city.lat}"
    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RoutingUnavailable(str(exc)) from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if data.get("code") == "NoRoute":
        raise NoRoute()
    if response.status_code != 200:
        raise RoutingUnavailable(f"OSRM answered {response.status_code}")
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingUnavailable(data.get("message") or data.get("code") or "no route")

    best = data["routes"][0]
    line = LineString(best["geometry"]["coordinates"])
    line = line.simplify(SIMPLIFY_DEG, preserve_topology=False)
    return RouteData(
        geometry=[(x, y) for x, y in line.coords],
        distance_mi=best["distance"] / MILE_M,
        duration_min=best["duration"] / 60,
    )
