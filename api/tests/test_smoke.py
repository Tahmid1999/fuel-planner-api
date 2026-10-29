import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from planner import routing
from planner.importers import import_prices
from planner.models import City
from tests.test_imports import SMALL

spec = importlib.util.spec_from_file_location(
    "smoke", Path(__file__).resolve().parents[2] / "scripts" / "smoke.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

# live_server needs real commits; serialized_rollback brings back the US row
# that a data migration creates and a transactional flush would wipe
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


class FakeRoute:
    status_code = 200

    def json(self):
        coords = [[-97.74, 30.27], [-92.0, 36.0], [-87.63, 41.88]]
        route = {"distance": 300 * 1609.344, "duration": 18000, "geometry": {"coordinates": coords}}
        return {"code": "Ok", "routes": [route]}


@pytest.fixture
def api(live_server, us, monkeypatch):
    monkeypatch.setattr(routing.requests, "get", lambda url, **kwargs: FakeRoute())
    City.objects.create(country=us, name="Austin", state="TX", lat=30.27, lng=-97.74)
    City.objects.create(country=us, name="Chicago", state="IL", lat=41.88, lng=-87.63)
    return live_server.url


def test_admin_login_page_loads(client):
    assert client.get("/admin/login/").status_code == 200


def load_prices(us):
    with SMALL.open(encoding="utf-8") as f:
        import_prices(f, us, "OPIS sample", dt.date(2025, 11, 28))


def test_smoke_passes_on_a_good_api(api, us, capsys):
    load_prices(us)
    assert smoke.main(["--api", api, "--wait", "5"]) == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert "ok  plan" in out


def test_smoke_reports_cors(api, us, capsys):
    load_prices(us)
    assert smoke.main(["--api", api, "--web", "http://wrong.example", "--wait", "5"]) == 1
    assert "FAIL cors: http://wrong.example not allowed" in capsys.readouterr().out


def test_smoke_fails_on_missing_prices(api, capsys):
    assert smoke.main(["--api", api, "--wait", "5"]) == 1
    assert "FAIL prices" in capsys.readouterr().out
