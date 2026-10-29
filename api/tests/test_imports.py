import datetime as dt
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from planner import importers
from planner.importers import active_price_list, import_cities, import_prices
from planner.models import City, Country, PriceList, Station, StationPrice

pytestmark = pytest.mark.django_db

SMALL = Path(__file__).parent / "fixtures" / "prices_small.csv"


def load(us, as_of=dt.date(2025, 11, 28), activate=True):
    with SMALL.open(encoding="utf-8") as f:
        return import_prices(f, us, "OPIS sample", as_of, activate=activate)


def test_us_exists_after_migrations():
    us = Country.objects.get(code="US")
    assert (us.price_model, us.distance_unit, us.volume_unit) == ("per_station", "mi", "gal")


def test_import_creates_stations_and_prices(us):
    report = load(us)
    assert report.created_stations == 8
    assert report.prices == 8
    tomah = Station.objects.get(opis_id="9")
    assert (tomah.lat, tomah.lng) == (31, -91)
    assert tomah.city.name == "Tomah"
    assert report.price_list.active


def test_duplicate_id_keeps_lowest_price(us):
    report = load(us)
    assert report.duplicates == 1
    price = StationPrice.objects.get(station__opis_id="20", price_list=report.price_list)
    assert price.price == Decimal("3.799")


def test_unknown_city_is_reported_not_fatal(us):
    report = load(us)
    assert report.skipped_unknown_city == ["Nowhere, ZZ"]
    assert not Station.objects.filter(opis_id="50").exists()


def test_reimport_reuses_stations(us):
    load(us)
    report = load(us, as_of=dt.date(2025, 12, 5))
    assert report.created_stations == 0
    assert Station.objects.count() == 8


def test_new_active_list_deactivates_old(us):
    first = load(us).price_list
    second = load(us, as_of=dt.date(2025, 12, 5)).price_list
    first.refresh_from_db()
    assert not first.active
    assert active_price_list("US") == second


def test_inactive_import_leaves_active_list_alone(us):
    first = load(us).price_list
    load(us, as_of=dt.date(2025, 12, 5), activate=False)
    assert active_price_list("US") == first


def test_active_price_list_none_when_empty():
    assert PriceList.objects.count() == 0
    assert active_price_list("US") is None


def test_import_cities_groups_by_city_and_state(monkeypatch):
    zips = [
        SimpleNamespace(major_city="Tomah", state="WI", lat=44.0, lng=-90.0, population=3000),
        SimpleNamespace(major_city="Tomah", state="WI", lat=44.4, lng=-90.4, population=1000),
        SimpleNamespace(major_city="Tomah", state="MN", lat=46.0, lng=-94.0, population=None),
    ]
    monkeypatch.setattr(importers, "_zipcodes", lambda: zips)
    us = Country.objects.get(code="US")
    assert import_cities(us) == 2
    wi = City.objects.get(name="Tomah", state="WI")
    assert wi.population == 4000
    assert wi.lat == pytest.approx(44.1)
    assert wi.lng == pytest.approx(-90.1)
    mn = City.objects.get(name="Tomah", state="MN")
    assert (mn.lat, mn.population) == (46.0, 0)


def test_import_prices_command(us, capsys):
    from django.core.management import call_command

    call_command("import_prices", str(SMALL), "--source", "OPIS sample", "--as-of", "2025-11-28")
    assert active_price_list("US").as_of == dt.date(2025, 11, 28)
    out = capsys.readouterr().out
    assert "8 prices" in out
    assert "Nowhere, ZZ" in out


def test_admin_upload_imports_file(us, admin_client):
    with SMALL.open("rb") as f:
        response = admin_client.post(
            "/admin/planner/pricelist/add/",
            {"country": "US", "source": "OPIS sample", "as_of": "2025-11-28", "file": f},
            follow=True,
        )
    assert response.status_code == 200
    assert PriceList.objects.count() == 1
    assert active_price_list("US").prices.count() == 8
    messages = [str(m) for m in response.context["messages"]]
    assert any("8 prices" in m for m in messages)


@pytest.mark.parametrize(
    "line,problem",
    [
        ("51,BAD,x,Tomah,WI,1,N/A", "row 12: price"),
        ("51,BAD,x,Tomah,WI,1,", "row 12: price"),
    ],
)
def test_bad_price_names_the_row(us, line, problem):
    import io

    text = SMALL.read_text(encoding="utf-8").rstrip("\n") + "\n" + line + "\n"
    with pytest.raises(ValueError, match=problem):
        import_prices(io.StringIO(text), us, "bad", dt.date(2025, 11, 28))
    assert PriceList.objects.count() == 0


def test_missing_column_rejected(us):
    import io

    with pytest.raises(ValueError, match="Retail Price"):
        import_prices(
            io.StringIO("OPIS Truckstop ID,City,State\n1,Tomah,WI\n"), us, "x", dt.date.today()
        )


def test_non_utf8_file_rejected(us):
    import io

    with pytest.raises(ValueError, match="UTF-8"):
        import_prices(io.BytesIO("City\nMontr\xe9al\n".encode("cp1252")), us, "x", dt.date.today())


def test_admin_rejects_bad_file_with_form_error(us, admin_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    bad = SimpleUploadedFile("p.csv", b"OPIS Truckstop ID,City,State\n1,Tomah,WI\n")
    response = admin_client.post(
        "/admin/planner/pricelist/add/",
        {"country": "US", "source": "x", "as_of": "2025-11-28", "file": bad},
    )
    assert response.status_code == 200
    assert "Retail Price" in str(response.context["adminform"].form.errors)
    assert PriceList.objects.count() == 0
