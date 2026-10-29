"""Cost of the same trips under three rules: the cheapest plan, the
quarter-tank habit, and the take-home's old rule.

    python scripts/compare_plans.py            # uses the saved routes, no network
    python scripts/compare_plans.py --fetch    # asks OSRM for the routes again first

Stations and prices come from the active price list, so run import_cities and
import_prices first. Prints a Markdown table.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
ROUTES_DIR = Path(__file__).resolve().parent / "routes"

PAIRS = [
    (("Austin", "TX"), ("Chicago", "IL")),
    (("Los Angeles", "CA"), ("Dallas", "TX")),
    (("Atlanta", "GA"), ("Denver", "CO")),
    (("Seattle", "WA"), ("Salt Lake City", "UT")),
    (("Miami", "FL"), ("New York", "NY")),
    (("Phoenix", "AZ"), ("Kansas City", "MO")),
]

HEADER = [
    "route",
    "miles",
    "stops new / habit / old",
    "cost new",
    "cost habit",
    "cost old",
    "new vs habit",
    "new vs old",
]


def setup_django():
    if str(API_DIR) not in sys.path:
        sys.path.insert(0, str(API_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fuelplanner.settings")
    import django

    django.setup()


def fetch_routes(folder):
    from planner.models import City
    from planner.routing import _fetch

    folder.mkdir(parents=True, exist_ok=True)
    for n, (start, end) in enumerate(PAIRS):
        if n:
            time.sleep(1)  # the public OSRM server allows about one request a second
        a = City.objects.get(country_id="US", name=start[0], state=start[1])
        b = City.objects.get(country_id="US", name=end[0], state=end[1])
        route = _fetch(a, b)
        data = {
            "from": a.label,
            "to": b.label,
            "distance_mi": route.distance_mi,
            "duration_min": route.duration_min,
            "geometry": [[round(x, 5), round(y, 5)] for x, y in route.geometry],
        }
        name = f"{a.name}-{b.name}".lower().replace(" ", "-")
        (folder / f"{name}.json").write_text(json.dumps(data))
        print(f"fetched {a.label} to {b.label}: {route.distance_mi:.0f} mi", file=sys.stderr)


def compare(route, corridor, v, threshold, max_detour_mi):
    from planner.fuel import Unreachable, plan_baseline, plan_cheapest, plan_old_rule

    miles = route["distance_mi"]
    candidates = corridor.candidates(route["geometry"], max_detour_mi, route_mi=miles)
    label = f"{route['from']} to {route['to']}"
    try:
        new = plan_cheapest(candidates, miles, v)
        habit = plan_baseline(candidates, miles, v, threshold)
        old = plan_old_rule(candidates, miles, v)
    except Unreachable as exc:
        gap = f"no plan: no fuel between mile {exc.from_mile:.0f} and {exc.to_mile:.0f}"
        return [label, f"{miles:.0f}", gap, "", "", "", "", ""]
    return [
        label,
        f"{miles:.0f}",
        f"{len(new.stops)} / {len(habit.stops)} / {len(old.stops)}",
        f"${new.cost:.2f}",
        f"${habit.cost:.2f}",
        f"${old.cost:.2f}",
        f"{habit.cost - new.cost:+.2f}",
        f"{old.cost - new.cost:+.2f}",
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fetch", action="store_true", help="refresh the routes from OSRM")
    parser.add_argument("--routes-dir", type=Path, default=ROUTES_DIR)
    args = parser.parse_args(argv)

    from django.conf import settings

    if not settings.configured:
        setup_django()

    from planner import defaults as d
    from planner.corridor import corridor_for
    from planner.importers import active_price_list
    from planner.trips import vehicle_from

    if args.fetch:
        fetch_routes(args.routes_dir)

    price_list = active_price_list("US")
    if price_list is None:
        sys.exit("no active price list: run import_cities and import_prices first")
    corridor = corridor_for(price_list)
    inputs = {
        "mpg": d.MPG,
        "tank_gal": d.TANK_GAL,
        "start_pct": d.START_PCT,
        "reserve_pct": d.RESERVE_PCT,
    }
    v = vehicle_from(inputs)
    threshold = v.tank * d.BASELINE_THRESHOLD_PCT / 100

    rows = []
    for path in sorted(args.routes_dir.glob("*.json")):
        route = json.loads(path.read_text())
        rows.append(compare(route, corridor, v, threshold, d.MAX_DETOUR_MI))

    print("| " + " | ".join(HEADER) + " |")
    print("|" + "---|" * len(HEADER))
    for row in rows:
        print("| " + " | ".join(row) + " |")
    print(
        f"\nPrices: {price_list.source}, as of {price_list.as_of}. Truck: {d.MPG} mpg, "
        f"{d.TANK_GAL} gal tank, starts {d.START_PCT}% full, keeps {d.RESERVE_PCT}%, "
        f"stations within {d.MAX_DETOUR_MI} mi of the route."
    )


if __name__ == "__main__":
    main()
