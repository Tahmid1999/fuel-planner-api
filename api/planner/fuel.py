"""Where to buy fuel along a fixed route, and what the trip costs.

No Django in here. Distances and volumes are whatever the caller uses
(miles and gallons for the US); prices are per unit of volume.
"""

from collections import deque
from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class Vehicle:
    tank: float
    mpg: float
    start: float  # fuel in the tank at mile 0
    reserve: float  # never planned below this


@dataclass(frozen=True)
class Candidate:
    key: str
    mile: float
    price: float
    detour_mi: float = 0.0


@dataclass
class Stop:
    candidate: Candidate
    gallons: float
    fuel_on_arrival: float


@dataclass
class Plan:
    stops: list[Stop]
    spend: float
    leftover_value: float
    cost: float
    gallons: float


class Unreachable(Exception):
    def __init__(self, from_mile, to_mile):
        super().__init__(f"no fuel between mile {from_mile:.1f} and mile {to_mile:.1f}")
        self.from_mile = from_mile
        self.to_mile = to_mile


def plan_cheapest(candidates, route_miles, v):
    """At each station: if a cheaper one (or the finish) is in reach, buy just
    enough to get to the nearest such point; otherwise fill the tank.

    tests/test_fuel_cheapest.py checks this against a brute-force solver.
    """
    stations = sorted(candidates, key=lambda c: c.mile)
    points = [c.mile for c in stations] + [route_miles]
    prices = [c.price for c in stations] + [0.0]
    usable_tank = v.tank - v.reserve
    reach = usable_tank * v.mpg

    fuel = v.start - v.reserve  # usable fuel, i.e. above the reserve
    fuel = _drive(fuel, 0.0, points[0], v.mpg)
    stops = []
    for i, station in enumerate(stations):
        target = None
        for j in range(i + 1, len(points)):
            if points[j] - station.mile > reach + EPS:
                break
            if prices[j] < station.price:
                target = j
                break
        if target is None:
            buy = usable_tank - fuel
        else:
            buy = max(0.0, (points[target] - station.mile) / v.mpg - fuel)
        if buy > EPS:
            stops.append(Stop(station, buy, fuel + v.reserve))
            fuel += buy
        fuel = _drive(fuel, station.mile, points[i + 1], v.mpg)

    return _priced(stops, route_miles, v)


def _drive(fuel, from_mile, to_mile, mpg):
    fuel -= (to_mile - from_mile) / mpg
    if fuel < -EPS:
        raise Unreachable(from_mile, to_mile)
    return fuel


def _priced(stops, route_miles, v):
    spend, leftover_value = cost_with_fifo(stops, route_miles, v)
    return Plan(
        stops=stops,
        spend=spend,
        leftover_value=leftover_value,
        cost=spend - leftover_value,
        gallons=sum(s.gallons for s in stops),
    )


def cost_with_fifo(stops, route_miles, v):
    """Money spent, and what the fuel left on arrival cost.

    The tank burns oldest fuel first. Fuel already in it at the start is free
    in every plan, so it goes in first at price 0.
    """
    tank = deque([[v.start, 0.0]])
    mile = 0.0
    spend = 0.0
    for stop in stops:
        _burn(tank, (stop.candidate.mile - mile) / v.mpg)
        mile = stop.candidate.mile
        tank.append([stop.gallons, stop.candidate.price])
        spend += stop.gallons * stop.candidate.price
    _burn(tank, (route_miles - mile) / v.mpg)
    return spend, sum(volume * price for volume, price in tank)


def _burn(tank, volume):
    while volume > EPS and tank:
        if tank[0][0] <= volume:
            volume -= tank.popleft()[0]
        else:
            tank[0][0] -= volume
            volume = 0.0


def plan_baseline(candidates, route_miles, v, threshold):
    """The habit the savings line is measured against: drive on, and fill to
    full at the first station where the next leg would leave less than
    `threshold` (a volume) in the tank.
    """
    stations = sorted(candidates, key=lambda c: c.mile)
    points = [c.mile for c in stations] + [route_miles]
    floor = max(threshold, v.reserve)

    fuel = v.start - v.reserve
    fuel = _drive(fuel, 0.0, points[0], v.mpg)
    stops = []
    for i, station in enumerate(stations):
        after_leg = fuel + v.reserve - (points[i + 1] - station.mile) / v.mpg
        if after_leg < floor - EPS:
            buy = v.tank - v.reserve - fuel
            if buy > EPS:
                stops.append(Stop(station, buy, fuel + v.reserve))
                fuel += buy
        fuel = _drive(fuel, station.mile, points[i + 1], v.mpg)

    return _priced(stops, route_miles, v)


def plan_old_rule(candidates, route_miles, v):
    """The take-home's choice of stops, re-costed like the other two.

    The old code jumped to the cheapest station within range until the finish
    was in range. Here it starts with the same tank and reserve, and buys just
    enough at each chosen stop to reach the next one, so only the choice of
    stops differs from the other plans.
    """
    stations = sorted(candidates, key=lambda c: c.mile)
    reach = (v.tank - v.reserve) * v.mpg

    chosen = []
    mile = 0.0
    in_range = (v.start - v.reserve) * v.mpg
    while mile + in_range < route_miles - EPS:
        window = [c for c in stations if mile < c.mile <= mile + in_range + EPS]
        if not window:
            ahead = [c.mile for c in stations if c.mile > mile]
            raise Unreachable(mile, ahead[0] if ahead else route_miles)
        best = min(window, key=lambda c: c.price)
        chosen.append(best)
        mile = best.mile
        in_range = reach

    fuel = v.start - v.reserve
    mile = 0.0
    stops = []
    for i, station in enumerate(chosen):
        fuel = _drive(fuel, mile, station.mile, v.mpg)
        mile = station.mile
        next_mile = chosen[i + 1].mile if i + 1 < len(chosen) else route_miles
        buy = max(0.0, (next_mile - mile) / v.mpg - fuel)
        if buy > EPS:
            stops.append(Stop(station, buy, fuel + v.reserve))
            fuel += buy
    _drive(fuel, mile, route_miles, v.mpg)

    return _priced(stops, route_miles, v)
