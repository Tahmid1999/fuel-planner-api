import datetime as dt
import math

import pytest

from planner.corridor import Corridor, corridor_for
from planner.importers import import_prices
from tests.test_imports import SMALL

EARTH_MI = 3958.8
ROUTE = [(-100.0, 40.0), (-98.0, 40.0), (-96.0, 40.0)]  # due east along 40N


def haversine_mi(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_MI * math.asin(math.sqrt(a))


def north_of(lat, miles):
    return lat + math.degrees(miles / EARTH_MI)


def test_station_on_route_has_zero_detour():
    [c] = Corridor([("a", 40.0, -98.0, 3.1)]).candidates(ROUTE, 3)
    assert c.key == "a"
    assert c.price == 3.1
    assert c.detour_mi == pytest.approx(0, abs=0.01)


def test_station_beyond_detour_excluded():
    corridor = Corridor([("a", north_of(40.0, 5), -98.0, 3.1)])
    assert corridor.candidates(ROUTE, 3) == []
    [c] = corridor.candidates(ROUTE, 6)
    assert c.detour_mi == pytest.approx(5, rel=0.02)


def test_mile_marker_close_to_haversine():
    lng = -100 + math.degrees(100 / (EARTH_MI * math.cos(math.radians(40))))
    [c] = Corridor([("a", 40.0, lng, 3.1)]).candidates(ROUTE, 3)
    assert c.mile == pytest.approx(haversine_mi(40, -100, 40, lng), rel=0.01)


def test_mile_marker_uses_local_latitude():
    # Miami-to-New-York-like route: 15 degrees of latitude change. Using one
    # mean cosine would be off by several percent at each end.
    route = [(-80.0, 25.0), (-80.0, 32.0), (-74.0, 40.0)]
    [c] = Corridor([("a", 32.0, -80.0, 3.1)]).candidates(route, 3)
    assert c.mile == pytest.approx(haversine_mi(25, -80, 32, -80), rel=0.01)


def test_station_past_the_finish_excluded():
    assert Corridor([("a", 40.0, -95.9, 3.1)]).candidates(ROUTE, 3) == []


def test_candidates_sorted_by_mile():
    stations = [("c", 40.0, -96.5, 3), ("a", 40.0, -99.5, 3), ("b", 40.01, -98.0, 3)]
    keys = [c.key for c in Corridor(stations).candidates(ROUTE, 3)]
    assert keys == ["a", "b", "c"]


@pytest.mark.django_db
def test_corridor_for_is_cached_per_price_list(us):
    with SMALL.open(encoding="utf-8") as f:
        first = import_prices(f, us, "OPIS sample", dt.date(2025, 11, 28)).price_list
    corridor = corridor_for(first)
    assert corridor_for(first) is corridor
    assert len(corridor.keys) == 8
    with SMALL.open(encoding="utf-8") as f:
        second = import_prices(f, us, "OPIS sample", dt.date(2025, 12, 5)).price_list
    assert corridor_for(second) is not corridor
