"""One trip plan, from two cities and a truck to the document the API returns."""

from . import defaults
from .corridor import corridor_for
from .fuel import Vehicle, plan_baseline, plan_cheapest
from .importers import active_price_list
from .models import Station, TripPlan
from .routing import get_route


class NoPrices(Exception):
    pass


def vehicle_from(inputs):
    tank = inputs["tank_gal"]
    return Vehicle(
        tank=tank,
        mpg=inputs["mpg"],
        start=tank * inputs["start_pct"] / 100,
        reserve=tank * inputs["reserve_pct"] / 100,
    )


def make_plan(from_city, to_city, inputs):
    """Raises fuel.Unreachable, routing.RoutingUnavailable or NoPrices; saves
    nothing unless a plan comes out."""
    price_list = active_price_list(from_city.country_id)
    if price_list is None:
        raise NoPrices()

    route = get_route(from_city, to_city)
    candidates = corridor_for(price_list).candidates(
        route.geometry, inputs["max_detour_mi"], route_mi=route.distance_mi
    )
    v = vehicle_from(inputs)
    threshold = v.tank * defaults.BASELINE_THRESHOLD_PCT / 100
    best = plan_cheapest(candidates, route.distance_mi, v)
    baseline = plan_baseline(candidates, route.distance_mi, v, threshold)

    keys = {s.candidate.key for s in best.stops + baseline.stops}
    stations = {
        s.opis_id: s
        for s in Station.objects.filter(country=from_city.country, opis_id__in=keys).select_related(
            "city"
        )
    }
    result = {
        "prices": {"source": price_list.source, "as_of": price_list.as_of.isoformat()},
        "route": {
            "distance_mi": round(route.distance_mi, 1),
            "duration_min": round(route.duration_min),
            "geometry": {"type": "LineString", "coordinates": [list(p) for p in route.geometry]},
        },
        "plan": _plan_doc(best, stations, v),
        "baseline": _plan_doc(baseline, stations, v),
        "savings": round(baseline.cost - best.cost, 2),
    }
    return TripPlan.objects.create(
        price_list=price_list,
        from_city=from_city,
        to_city=to_city,
        inputs=inputs,
        result=result,
    )


def _plan_doc(plan, stations, v):
    return {
        "stops": [_stop_doc(s, stations[s.candidate.key], v) for s in plan.stops],
        "spend": round(plan.spend, 2),
        "leftover_value": round(plan.leftover_value, 2),
        "cost": round(plan.cost, 2),
        "gallons": round(plan.gallons, 1),
    }


def _stop_doc(stop, station, v):
    c = stop.candidate
    return {
        "opis_id": station.opis_id,
        "name": station.name,
        "address": station.address,
        "city": station.city.name,
        "state": station.city.state,
        "lat": round(station.lat, 4),
        "lng": round(station.lng, 4),
        "mile": round(c.mile, 1),
        "detour_mi": round(c.detour_mi, 1),
        # there and back again
        "detour_gal": round(2 * c.detour_mi / v.mpg, 1),
        "price": round(c.price, 3),
        "gallons": round(stop.gallons, 1),
        "cost": round(stop.gallons * c.price, 2),
    }


def plan_document(trip):
    def city(c):
        return {"id": c.id, "label": c.label, "lat": c.lat, "lng": c.lng}

    return {
        "id": trip.id,
        "created_at": trip.created_at.isoformat(),
        "from": city(trip.from_city),
        "to": city(trip.to_city),
        "inputs": trip.inputs,
        **trip.result,
    }
