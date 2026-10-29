import random

import pytest

from planner.fuel import Candidate, Stop, Unreachable, Vehicle, cost_with_fifo, plan_cheapest
from tests.oracle import cheapest_spend


def test_no_stop_when_start_fuel_covers_trip():
    v = Vehicle(tank=100, mpg=1, start=60, reserve=10)
    plan = plan_cheapest([Candidate("a", 20, 3)], 40, v)
    assert plan.stops == []
    assert plan.spend == 0


def test_fills_up_before_expensive_stretch():
    v = Vehicle(tank=100, mpg=1, start=20, reserve=0)
    stations = [Candidate("a", 10, 2.00), Candidate("b", 100, 4.00)]
    plan = plan_cheapest(stations, 180, v)
    assert [(s.candidate.key, s.gallons) for s in plan.stops] == [("a", 90), ("b", 70)]
    assert plan.stops[0].fuel_on_arrival == 10
    assert plan.spend == pytest.approx(460)
    assert plan.spend == pytest.approx(cheapest_spend(stations, 180, v))


def test_buys_only_to_reach_nearest_cheaper():
    v = Vehicle(tank=100, mpg=1, start=15, reserve=0)
    plan = plan_cheapest([Candidate("a", 10, 4), Candidate("b", 60, 2)], 150, v)
    assert plan.stops[0].candidate.key == "a"
    assert plan.stops[0].gallons == pytest.approx(45)


def test_gap_longer_than_range_raises():
    v = Vehicle(tank=100, mpg=1, start=50, reserve=10)
    with pytest.raises(Unreachable) as exc:
        plan_cheapest([Candidate("a", 10, 3), Candidate("b", 120, 3)], 150, v)
    assert (exc.value.from_mile, exc.value.to_mile) == (10, 120)


def test_first_station_out_of_reach_raises_from_zero():
    v = Vehicle(tank=100, mpg=1, start=30, reserve=10)
    with pytest.raises(Unreachable) as exc:
        plan_cheapest([Candidate("a", 50, 3)], 100, v)
    assert (exc.value.from_mile, exc.value.to_mile) == (0, 50)


def random_case(rng):
    route = rng.randint(20, 300)
    tank = rng.randint(20, 60)
    reserve = rng.randint(0, 10)
    v = Vehicle(tank=tank, mpg=1, start=rng.randint(reserve, tank), reserve=reserve)
    stations = [
        Candidate(str(i), rng.randint(1, route - 1), rng.randint(1, 9))
        for i in range(rng.randint(0, 12))
    ]
    return stations, route, v


def test_matches_oracle_on_random_routes():
    rng = random.Random(7)
    feasible = 0
    for _ in range(500):
        stations, route, v = random_case(rng)
        expected = cheapest_spend(stations, route, v)
        if expected is None:
            with pytest.raises(Unreachable):
                plan_cheapest(stations, route, v)
        else:
            feasible += 1
            assert plan_cheapest(stations, route, v).spend == pytest.approx(expected)
    # guard against a generator that only makes impossible trips
    assert feasible > 100


def test_fifo_leftover_value():
    v = Vehicle(tank=100, mpg=1, start=30, reserve=0)
    stop = Stop(Candidate("a", 0, 3), gallons=50, fuel_on_arrival=30)
    spend, leftover_value = cost_with_fifo([stop], 40, v)
    assert spend == 150
    assert leftover_value == pytest.approx(120)
