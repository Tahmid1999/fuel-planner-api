import random

import pytest

from planner.fuel import (
    Candidate,
    Unreachable,
    Vehicle,
    plan_baseline,
    plan_cheapest,
    plan_old_rule,
)
from tests.test_fuel_cheapest import random_case


def test_baseline_fills_to_full_below_threshold():
    v = Vehicle(tank=100, mpg=1, start=50, reserve=0)
    stations = [Candidate(str(m), m, 3) for m in (20, 40, 70, 90)]
    plan = plan_baseline(stations, 120, v, threshold=25)
    assert [s.candidate.mile for s in plan.stops] == [20, 90]
    assert all(s.fuel_on_arrival + s.gallons == pytest.approx(100) for s in plan.stops)


def test_baseline_leftover_is_credited():
    v = Vehicle(tank=100, mpg=1, start=50, reserve=0)
    stations = [Candidate(str(m), m, 3) for m in (20, 40, 70, 90)]
    plan = plan_baseline(stations, 120, v, threshold=25)
    assert plan.leftover_value == pytest.approx(210)
    assert plan.cost == pytest.approx(plan.spend - plan.leftover_value)


def test_baseline_gap_raises():
    v = Vehicle(tank=100, mpg=1, start=50, reserve=10)
    with pytest.raises(Unreachable):
        plan_baseline([Candidate("a", 10, 3), Candidate("b", 120, 3)], 150, v, threshold=25)


def test_old_rule_can_cost_more():
    # A is cheap but the old rule only stops there because it has to, buys
    # just enough to reach C (the cheapest in A's range) and pays C's price
    # for the rest of the trip.
    v = Vehicle(tank=100, mpg=1, start=20, reserve=0)
    stations = [Candidate("a", 10, 2.0), Candidate("b", 100, 4.0), Candidate("c", 105, 3.9)]
    old = plan_old_rule(stations, 180, v)
    assert [s.candidate.key for s in old.stops] == ["a", "c"]
    assert old.cost == pytest.approx(462.5)
    assert plan_cheapest(stations, 180, v).cost == pytest.approx(453)


def test_cheapest_never_costs_more_than_others():
    rng = random.Random(11)
    feasible = 0
    for _ in range(300):
        stations, route, v = random_case(rng)
        try:
            best = plan_cheapest(stations, route, v)
        except Unreachable:
            continue
        feasible += 1
        threshold = v.tank * 0.25
        assert best.cost <= plan_baseline(stations, route, v, threshold).cost + 1e-9
        assert best.cost <= plan_old_rule(stations, route, v).cost + 1e-9
    assert feasible > 40
