import datetime as dt
import io

import pytest
import requests

from planner import routing
from planner.importers import import_prices
from planner.models import City, Country, RouteCache, TripPlan

pytestmark = pytest.mark.django_db

# A road due east along 40N with a town every half degree of longitude. The
# straight line is 212 miles; OSRM says the road is 240, so stops are placed
# by share of the road (every 30 miles).
STATION_LNGS = [-99.5, -99.0, -98.5, -98.0, -97.5, -97.0, -96.5]
PRICES = [3.10, 3.90, 3.20, 2.80, 3.70, 3.60, 3.50]
ROUTE_MI = 240.0
SMALL_TRUCK = {"mpg": 6.5, "tank_gal": 20, "start_pct": 50, "reserve_pct": 15}


class FakeResponse:
    status_code = 200

    def json(self):
        coords = [[-100.0, 40.0], [-98.0, 40.0], [-96.0, 40.0]]
        route = {
            "distance": ROUTE_MI * 1609.344,
            "duration": 12000,
            "geometry": {"coordinates": coords},
        }
        return {"code": "Ok", "routes": [route]}


@pytest.fixture
def osrm(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(routing.requests, "get", fake_get)
    return calls


@pytest.fixture
def world():
    us = Country.objects.get(code="US")
    west = City.objects.create(country=us, name="Westend", state="KS", lat=40, lng=-100)
    east = City.objects.create(country=us, name="Eastend", state="KS", lat=40, lng=-96)
    return us, west, east


def load_prices(us, lngs=STATION_LNGS, prices=PRICES):
    lines = ["OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price"]
    for i, (lng, price) in enumerate(zip(lngs, prices, strict=True)):
        City.objects.create(country=us, name=f"Town {i}", state="KS", lat=40, lng=lng)
        lines.append(f'{100 + i},STOP {i},"I-00, EXIT {i}",Town {i},KS,1,{price}')
    import_prices(io.StringIO("\n".join(lines)), us, "test prices", dt.date(2025, 11, 28))


def post_plan(client, west, east, **extra):
    body = {"from_city": west.id, "to_city": east.id, **SMALL_TRUCK, **extra}
    return client.post("/api/plans/", body, content_type="application/json")


def test_create_plan_returns_201_and_location(client, osrm, world):
    us, west, east = world
    load_prices(us)
    response = post_plan(client, west, east)
    assert response.status_code == 201
    doc = response.json()
    assert response["Location"] == f"/api/plans/{doc['id']}/"
    assert len(doc["id"]) == 12
    assert doc["from"]["label"] == "Westend, KS"
    assert doc["prices"] == {"source": "test prices", "as_of": "2025-11-28"}
    assert doc["route"]["distance_mi"] == 240.0
    assert doc["route"]["geometry"]["type"] == "LineString"
    stops = doc["plan"]["stops"]
    assert stops, "a 20 gallon tank cannot do 240 miles on half a tank"
    assert [s["mile"] for s in stops] == sorted(s["mile"] for s in stops)
    first = stops[0]
    fields = {"opis_id", "name", "address", "city", "state", "lat", "lng", "mile"}
    fields |= {"detour_mi", "detour_gal", "price", "gallons", "cost"}
    assert set(first) == fields
    assert first["cost"] == pytest.approx(first["gallons"] * first["price"], abs=0.2)


def test_get_saved_plan_returns_same_document(client, osrm, world):
    us, west, east = world
    load_prices(us)
    created = post_plan(client, west, east).json()
    fetched = client.get(f"/api/plans/{created['id']}/")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_unknown_plan_404(client):
    assert client.get("/api/plans/nope/").status_code == 404


def test_defaults_fill_missing_inputs(client, osrm, world):
    us, west, east = world
    load_prices(us)
    body = {"from_city": west.id, "to_city": east.id}
    doc = client.post("/api/plans/", body, content_type="application/json").json()
    assert doc["inputs"] == {
        "mpg": 6.5,
        "tank_gal": 150.0,
        "start_pct": 50.0,
        "reserve_pct": 15.0,
        "max_detour_mi": 3.0,
    }


def test_savings_equals_baseline_minus_plan(client, osrm, world):
    us, west, east = world
    load_prices(us)
    doc = post_plan(client, west, east).json()
    assert doc["savings"] == pytest.approx(doc["baseline"]["cost"] - doc["plan"]["cost"], abs=0.011)
    assert doc["savings"] > 0
    plan = doc["plan"]
    assert plan["cost"] == pytest.approx(plan["spend"] - plan["leftover_value"], abs=0.011)


def test_second_identical_plan_makes_no_routing_call(client, osrm, world):
    us, west, east = world
    load_prices(us)
    post_plan(client, west, east)
    post_plan(client, west, east)
    assert len(osrm) == 1


def test_same_city_rejected_400(client, world):
    _, west, _ = world
    response = post_plan(client, west, west)
    assert response.status_code == 400
    assert "to_city" in response.json()


def test_start_below_reserve_rejected_400(client, world):
    _, west, east = world
    response = post_plan(client, west, east, start_pct=10, reserve_pct=15)
    assert response.status_code == 400
    assert "start_pct" in response.json()


@pytest.mark.parametrize(
    "field,value",
    [
        ("mpg", 0),
        ("mpg", 20),
        ("tank_gal", 0),
        ("reserve_pct", 50),
        ("start_pct", 101),
        ("max_detour_mi", 11),
    ],
)
def test_out_of_range_inputs_rejected_400(client, world, field, value):
    _, west, east = world
    response = post_plan(client, west, east, **{field: value})
    assert response.status_code == 400
    assert field in response.json()


def test_unknown_city_400(client, world):
    _, west, _ = world
    body = {"from_city": west.id, "to_city": 999999}
    response = client.post("/api/plans/", body, content_type="application/json")
    assert response.status_code == 400
    assert "to_city" in response.json()


def test_gap_too_long_returns_422_with_miles(client, osrm, world):
    us, west, east = world
    load_prices(us, lngs=[-99.5, -96.5], prices=[3.0, 3.0])
    response = post_plan(client, west, east)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "no fuel stop within range between mile 30.0 and mile 210.0 (180.0 mi)"
    assert TripPlan.objects.count() == 0


def test_routing_down_returns_502(client, monkeypatch, world):
    us, west, east = world
    load_prices(us)

    def down(url, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr(routing.requests, "get", down)
    response = post_plan(client, west, east)
    assert response.status_code == 502
    assert response.json() == {"detail": "routing service unavailable, try again shortly"}
    assert RouteCache.objects.count() == 0


def test_no_active_prices_returns_503(client, osrm, world):
    _, west, east = world
    response = post_plan(client, west, east)
    assert response.status_code == 503
    assert response.json() == {"detail": "no prices loaded"}
    assert client.get("/api/prices/active/").status_code == 503


def test_active_prices(client, world):
    us, _, _ = world
    load_prices(us)
    assert client.get("/api/prices/active/").json() == {
        "source": "test prices",
        "as_of": "2025-11-28",
        "station_count": 7,
    }


def test_city_search_prefix_and_order(client):
    us = Country.objects.get(code="US")
    towns = [("Chicago Heights", 30000), ("Chicago", 2700000), ("Chico", 100000)]
    towns.append(("North Chicago", 30000))
    for name, pop in towns:
        City.objects.create(country=us, name=name, state="IL", lat=41, lng=-87, population=pop)
    found = client.get("/api/cities/?q=CHIC").json()
    assert [c["name"] for c in found] == ["Chicago", "Chico", "Chicago Heights"]
    assert found[0]["label"] == "Chicago, IL"
    assert set(found[0]) == {"id", "name", "state", "label"}


def test_city_search_caps_at_ten(client):
    us = Country.objects.get(code="US")
    for i in range(12):
        City.objects.create(country=us, name=f"Springfield {i}", state="IL", lat=0, lng=0)
    assert len(client.get("/api/cities/?q=spr").json()) == 10


def test_city_search_short_query_empty(client):
    us = Country.objects.get(code="US")
    City.objects.create(country=us, name="Chicago", state="IL", lat=41, lng=-87)
    assert client.get("/api/cities/?q=c").json() == []
    assert client.get("/api/cities/").json() == []


def test_schema_and_docs_load(client):
    schema = client.get("/api/schema/")
    assert schema.status_code == 200
    assert b"/api/plans/" in schema.content
    assert client.get("/api/docs/").status_code == 200


def test_schema_has_no_warnings(tmp_path):
    from django.core.management import call_command

    call_command("spectacular", "--file", str(tmp_path / "s.yml"), "--validate", "--fail-on-warn")
