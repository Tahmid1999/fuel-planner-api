"""Slow exact solver used only to check plan_cheapest.

Works on whole gallons, so callers pick mpg 1 and integer miles. State is the
usable fuel on arrival at each point; at a station any amount can be bought.
"""


def cheapest_spend(candidates, route_miles, v):
    cap = round(v.tank - v.reserve)
    stations = sorted(candidates, key=lambda c: c.mile)
    miles = [0] + [c.mile for c in stations] + [route_miles]

    best = {round(v.start - v.reserve): 0.0}
    for idx in range(len(miles) - 1):
        if idx > 0:
            price = stations[idx - 1].price
            bought = {}
            for fuel, spend in best.items():
                for k in range(cap - fuel + 1):
                    total = spend + k * price
                    if total < bought.get(fuel + k, float("inf")):
                        bought[fuel + k] = total
            best = bought
        leg = round((miles[idx + 1] - miles[idx]) / v.mpg)
        best = {fuel - leg: spend for fuel, spend in best.items() if fuel >= leg}
        if not best:
            return None
    return min(best.values())
