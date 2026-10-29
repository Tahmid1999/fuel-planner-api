import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import City, PriceList, Station, StationPrice


@dataclass
class ImportReport:
    price_list: PriceList
    created_stations: int = 0
    prices: int = 0
    skipped_unknown_city: list[str] = field(default_factory=list)
    duplicates: int = 0

    def summary(self):
        text = (
            f"{self.prices} prices, {self.created_stations} new stations, "
            f"{self.duplicates} duplicate rows dropped"
        )
        if self.skipped_unknown_city:
            text += f", {len(self.skipped_unknown_city)} cities not found"
        return text


COLUMNS = ["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Retail Price"]


def read_price_rows(fileobj):
    """Parse the CSV, one row per station id, keeping the lowest price when an
    id repeats. Raises ValueError saying what is wrong and where."""
    text = fileobj.read()
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("the file is not UTF-8; save it as CSV UTF-8 and try again") from exc

    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError("missing columns: " + ", ".join(missing))

    rows = {}
    duplicates = 0
    for row in reader:
        line = reader.line_num
        opis_id = (row["OPIS Truckstop ID"] or "").strip()
        if not opis_id:
            raise ValueError(f"row {line}: no OPIS Truckstop ID")
        try:
            price = Decimal((row["Retail Price"] or "").strip()).quantize(Decimal("0.001"))
        except InvalidOperation:
            price = None
        if price is None or not price.is_finite() or not 0 < price < 100:
            raise ValueError(f"row {line}: price {row['Retail Price']!r} is not a number")
        row["price"] = price
        if opis_id in rows:
            duplicates += 1
            if price >= rows[opis_id]["price"]:
                continue
        rows[opis_id] = row
    return rows, duplicates


def import_prices(fileobj, country, source, as_of, activate=True):
    """Load an OPIS-style CSV into a new price list.

    A station id can appear several times with different prices; the lowest
    one is kept. Stations get their town's coordinates.
    """
    rows, duplicates = read_price_rows(fileobj)

    cities = {(c.name.lower(), c.state): c for c in City.objects.filter(country=country)}
    existing = {s.opis_id: s for s in Station.objects.filter(country=country)}
    unknown = set()
    new, changed, prices = [], [], []

    for opis_id, row in rows.items():
        city_name, state = row["City"].strip(), row["State"].strip()
        city = cities.get((city_name.lower(), state))
        if city is None:
            unknown.add(f"{city_name}, {state}")
            continue
        values = {
            "name": row["Truckstop Name"].strip(),
            "address": " ".join(row["Address"].split()),
            "city": city,
            "lat": city.lat,
            "lng": city.lng,
        }
        station = existing.get(opis_id)
        if station is None:
            station = Station(country=country, opis_id=opis_id, **values)
            new.append(station)
        else:
            for name, value in values.items():
                setattr(station, name, value)
            changed.append(station)
        prices.append((station, row["price"]))

    with transaction.atomic():
        price_list = PriceList.objects.create(country=country, source=source, as_of=as_of)
        Station.objects.bulk_create(new, batch_size=1000)
        Station.objects.bulk_update(
            changed, ["name", "address", "city", "lat", "lng"], batch_size=1000
        )
        StationPrice.objects.bulk_create(
            [StationPrice(price_list=price_list, station=s, price=p) for s, p in prices],
            batch_size=1000,
        )
        if activate:
            price_list.active = True
            price_list.save()

    return ImportReport(
        price_list=price_list,
        created_stations=len(new),
        prices=len(prices),
        skipped_unknown_city=sorted(unknown),
        duplicates=duplicates,
    )


def active_price_list(country_code):
    return PriceList.objects.filter(country_id=country_code, active=True).first()


def _zipcodes():
    # Imported here: building the search engine downloads uszipcode's
    # database (about 10 MB) the first time it runs.
    from uszipcode import SearchEngine
    from uszipcode.model import SimpleZipcode

    engine = SearchEngine()
    return engine.ses.query(SimpleZipcode).all()


def import_cities(country):
    """One City per (major city, state) from uszipcode, placed at the
    population-weighted centre of its zipcodes."""
    groups = defaultdict(list)
    for z in _zipcodes():
        if z.major_city and z.state and z.lat is not None and z.lng is not None:
            groups[(z.major_city, z.state)].append(z)

    cities = []
    for (name, state), zips in groups.items():
        population = sum(z.population or 0 for z in zips)
        weights = [z.population or 0 for z in zips] if population else [1] * len(zips)
        total = sum(weights)
        cities.append(
            City(
                country=country,
                name=name,
                state=state,
                lat=sum(z.lat * w for z, w in zip(zips, weights, strict=True)) / total,
                lng=sum(z.lng * w for z, w in zip(zips, weights, strict=True)) / total,
                population=population,
            )
        )

    return _upsert_cities(cities)


def load_cities_csv(fileobj, country):
    """Cities from the file export_cities writes (name,state,lat,lng,population)."""
    cities = [
        City(
            country=country,
            name=row["name"],
            state=row["state"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            population=int(row["population"]),
        )
        for row in csv.DictReader(fileobj)
    ]
    return _upsert_cities(cities)


def _upsert_cities(cities):
    City.objects.bulk_create(
        cities,
        batch_size=1000,
        update_conflicts=True,
        unique_fields=["country", "name", "state"],
        update_fields=["lat", "lng", "population"],
    )
    return len(cities)
