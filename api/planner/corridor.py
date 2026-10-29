"""Which stations lie along a route, and at what mile.

Stations and the route go into Web Mercator (EPSG:3857) so Shapely can do
plain planar geometry. Mercator stretches lengths by 1/cos(latitude), so
every distance is scaled back with the cosine of the latitude where it was
measured: per route segment for mile markers, at the station for detours.
"""

import math
from bisect import bisect_right
from itertools import accumulate

import shapely
from pyproj import Transformer
from shapely import LineString, STRtree

from .fuel import Candidate
from .models import StationPrice

MILE_M = 1609.344
_to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


class Corridor:
    def __init__(self, stations):
        """stations: [(key, lat, lng, price)]"""
        self.keys = [s[0] for s in stations]
        self.lats = [s[1] for s in stations]
        self.prices = [float(s[3]) for s in stations]
        xs, ys = _to_mercator.transform([s[2] for s in stations], self.lats)
        self.points = shapely.points(xs, ys)
        self.tree = STRtree(self.points)

    def candidates(self, route, max_detour_mi):
        """route: [(lng, lat)] from start to finish."""
        lngs = [p[0] for p in route]
        lats = [p[1] for p in route]
        xs, ys = _to_mercator.transform(lngs, lats)
        line = LineString(list(zip(xs, ys, strict=True)))

        # Running length along the route, in Mercator metres and in true miles.
        cos = [math.cos(math.radians((a + b) / 2)) for a, b in zip(lats, lats[1:], strict=False)]
        pieces = [
            math.hypot(x2 - x1, y2 - y1)
            for x1, y1, x2, y2 in zip(xs, ys, xs[1:], ys[1:], strict=False)
        ]
        run_merc = [0.0, *accumulate(pieces)]
        run_mi = [0.0, *accumulate(p * c / MILE_M for p, c in zip(pieces, cos, strict=True))]

        widest = max_detour_mi * MILE_M / min(math.cos(math.radians(lat)) for lat in lats)
        found = []
        for i in self.tree.query(line, predicate="dwithin", distance=widest):
            point = self.points[i]
            detour = line.distance(point) * math.cos(math.radians(self.lats[i])) / MILE_M
            if detour > max_detour_mi:
                continue
            along = line.project(point)
            # Past the finish: buying there doesn't help this trip.
            if along >= line.length - 1e-6:
                continue
            found.append(
                Candidate(self.keys[i], _to_miles(along, run_merc, run_mi), self.prices[i], detour)
            )
        return sorted(found, key=lambda c: c.mile)


def _to_miles(along, run_merc, run_mi):
    k = min(max(bisect_right(run_merc, along) - 1, 0), len(run_merc) - 2)
    span = run_merc[k + 1] - run_merc[k]
    share = (along - run_merc[k]) / span if span else 0.0
    return run_mi[k] + share * (run_mi[k + 1] - run_mi[k])


_cache = {}


def corridor_for(price_list):
    """One Corridor per price list, built on first use. Only the latest is
    kept: plans are always made against the active list."""
    # uploaded_at too: SQLite can hand a deleted list's id to a new one.
    key = (price_list.pk, price_list.uploaded_at)
    if key not in _cache:
        _cache.clear()
        rows = StationPrice.objects.filter(price_list=price_list).values_list(
            "station__opis_id", "station__lat", "station__lng", "price"
        )
        _cache[key] = Corridor(list(rows))
    return _cache[key]
