import datetime as dt
import io
import json

import pytest

from planner import routing
from planner.importers import import_prices
from planner.models import City, Country
from scripts import compare_plans

pytestmark = pytest.mark.django_db

PRICES = [3.6, 3.1, 3.9, 3.4, 2.9, 3.8, 3.5, 3.3, 3.7, 3.0, 3.6, 3.2, 3.9, 3.1, 3.5]


def load_stations():
    us = Country.objects.get(code="US")
    lines = ["OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price"]
    for i, price in enumerate(PRICES):
        City.objects.create(country=us, name=f"Town {i}", state="KS", lat=40, lng=-99 + i)
        lines.append(f"{i},STOP {i},I-70,Town {i},KS,1,{price}")
    import_prices(io.StringIO("\n".join(lines)), us, "test prices", dt.date(2025, 11, 28))


def write_route(folder, name, start_lng, end_lng, miles):
    route = {
        "from": f"{name} A, KS",
        "to": f"{name} B, KS",
        "distance_mi": miles,
        "duration_min": miles,
        "geometry": [[start_lng, 40.0], [end_lng, 40.0]],
    }
    (folder / f"{name}.json").write_text(json.dumps(route))


def test_script_runs_offline_and_prints_table(tmp_path, capsys, monkeypatch):
    load_stations()
    write_route(tmp_path, "long", -100.0, -84.5, 900)
    write_route(tmp_path, "short", -99.5, -95.5, 230)

    def no_network(*args, **kwargs):
        raise AssertionError("the script went online without --fetch")

    monkeypatch.setattr(routing.requests, "get", no_network)
    compare_plans.main(["--routes-dir", str(tmp_path)])

    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("|")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    assert header == [
        "route",
        "miles",
        "stops new / habit / old",
        "cost new",
        "cost habit",
        "cost old",
        "new vs habit",
        "new vs old",
    ]
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in lines[2:]]
    assert [r[0] for r in rows] == ["long A, KS to long B, KS", "short A, KS to short B, KS"]
    for row in rows:
        new, habit, old = (float(c.lstrip("$")) for c in row[3:6])
        assert new <= habit
        assert new <= old
    assert float(rows[0][3].lstrip("$")) > 0
