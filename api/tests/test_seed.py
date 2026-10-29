import gzip
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings

from planner.importers import active_price_list, load_cities_csv
from planner.models import City, Country, PriceList
from tests.test_imports import SMALL

pytestmark = pytest.mark.django_db

CITIES = Path(__file__).parent / "fixtures" / "cities_small.csv"
small_seed = override_settings(SEED_CITIES=CITIES, SEED_PRICES=SMALL)


def seed(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


@small_seed
def test_seed_loads_cities_and_prices():
    seed()
    assert City.objects.count() == 7
    assert active_price_list("US").prices.count() == 8


@small_seed
def test_seed_if_empty_is_a_no_op_the_second_time():
    seed("--if-empty")
    assert "already seeded" in seed("--if-empty")
    assert PriceList.objects.count() == 1


@small_seed
def test_seed_is_all_or_nothing(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("container stopped mid-seed")

    monkeypatch.setattr("planner.management.commands.seed_demo.import_prices", broken)
    with pytest.raises(RuntimeError):
        seed()
    assert City.objects.count() == 0
    assert PriceList.objects.count() == 0


def test_export_then_load_round_trips(tmp_path):
    us = Country.objects.get(code="US")
    for name, state, lat, lng in [("Austin", "TX", 30.27, -97.74), ("Aurora", "IL", 41.76, -88.32)]:
        City.objects.create(country=us, name=name, state=state, lat=lat, lng=lng, population=5)
    before = sorted(City.objects.values_list("name", "state", "lat", "lng", "population"))
    out = tmp_path / "cities.csv.gz"
    call_command("export_cities", "--out", str(out), stdout=StringIO())
    City.objects.all().delete()
    with gzip.open(out, "rt", encoding="utf-8") as f:
        assert load_cities_csv(f, us) == 2
    assert sorted(City.objects.values_list("name", "state", "lat", "lng", "population")) == before
