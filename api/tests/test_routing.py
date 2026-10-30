import pytest
import requests

from planner import routing
from planner.models import City, RouteCache
from planner.routing import NoRoute, RoutingUnavailable, get_route

pytestmark = pytest.mark.django_db


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


def osrm_ok(distance_m=160934.0):
    coords = [[-97.74, 30.27], [-97.0, 32.0], [-92.315, 36.9401], [-87.63, 41.88]]
    return {
        "code": "Ok",
        "routes": [{"distance": distance_m, "duration": 3600, "geometry": {"coordinates": coords}}],
    }


class Calls(list):
    response = None  # set by a test to answer with something other than a good route


@pytest.fixture
def calls(monkeypatch):
    seen = Calls()

    def fake_get(url, **kwargs):
        seen.append((url, kwargs))
        if seen.response:
            return seen.response(url, kwargs)
        return FakeResponse(osrm_ok())

    monkeypatch.setattr(routing.requests, "get", fake_get)
    return seen


@pytest.fixture
def pair(us):
    return City.objects.get(name="Jarrell"), City.objects.get(name="Tomah")


def test_second_call_uses_cache(calls, pair):
    first = get_route(*pair)
    second = get_route(*pair)
    assert len(calls) == 1
    assert second.geometry == first.geometry


def test_user_agent_and_timeout_sent(calls, pair):
    get_route(*pair)
    url, kwargs = calls[0]
    assert url.startswith("https://router.project-osrm.org/route/v1/driving/")
    assert kwargs["headers"]["User-Agent"].startswith("haulfill (")
    assert kwargs["timeout"] == 20


def test_coordinates_in_lng_lat_order(calls, pair):
    start, end = pair
    get_route(start, end)
    assert f"{start.lng},{start.lat};{end.lng},{end.lat}" in calls[0][0]


def test_distance_converted_to_miles(calls, pair):
    route = get_route(*pair)
    assert route.distance_mi == pytest.approx(100.0, rel=1e-4)
    assert route.duration_min == 60


def test_geometry_is_simplified(calls, pair):
    # the third point sits 0.0001 degrees off a straight line, so it goes
    assert len(get_route(*pair).geometry) == 3


def test_timeout_raises_unavailable_and_caches_nothing(calls, pair):
    def boom(url, kwargs):
        raise requests.Timeout()

    calls.response = boom
    with pytest.raises(RoutingUnavailable):
        get_route(*pair)
    assert RouteCache.objects.count() == 0


def test_http_error_raises_unavailable(calls, pair):
    calls.response = lambda url, kwargs: FakeResponse({}, status=429)
    with pytest.raises(RoutingUnavailable):
        get_route(*pair)


def test_non_ok_code_raises_unavailable(calls, pair):
    calls.response = lambda url, kwargs: FakeResponse({"code": "InvalidQuery", "routes": []})
    with pytest.raises(RoutingUnavailable):
        get_route(*pair)
    assert RouteCache.objects.count() == 0


def test_garbage_body_raises_unavailable(calls, pair):
    class Garbage:
        status_code = 200

        def json(self):
            raise requests.JSONDecodeError("Expecting value", "<html>", 0)

    calls.response = lambda url, kwargs: Garbage()
    with pytest.raises(RoutingUnavailable):
        get_route(*pair)


def test_no_route_is_not_a_server_outage(calls, pair):
    body = {"code": "NoRoute", "message": "Impossible route between points"}
    calls.response = lambda url, kwargs: FakeResponse(body, status=400)
    with pytest.raises(NoRoute):
        get_route(*pair)
    assert RouteCache.objects.count() == 0


def test_concurrent_first_requests_do_not_500(calls, pair, monkeypatch):
    start, end = pair
    real_fetch = routing._fetch

    def fetch_while_another_request_saves(a, b):
        route = real_fetch(a, b)
        # the other request finished first and stored the same pair
        RouteCache.objects.create(
            from_city=a,
            to_city=b,
            geometry=[list(p) for p in route.geometry],
            distance_mi=route.distance_mi,
            duration_min=route.duration_min,
        )
        return route

    monkeypatch.setattr(routing, "_fetch", fetch_while_another_request_saves)
    route = get_route(start, end)
    assert RouteCache.objects.count() == 1
    stored = RouteCache.objects.get()
    assert route.distance_mi == stored.distance_mi
