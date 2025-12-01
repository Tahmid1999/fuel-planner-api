from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from uszipcode import SearchEngine

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "fuel-prices-for-be-assessment.csv"
DATA_DIR = ROOT / "data"
OUTPUT_JSON = DATA_DIR / "stations_with_coords.json"


@dataclass
class StationRecord:
    opis_id: str
    name: str
    address: str
    city: str
    state: str
    rack_id: str
    retail_price: float
    latitude: float
    longitude: float


def normalize_city(value: str) -> str:
    return " ".join(value.split()).title()


def normalize_state(value: str) -> str:
    return value.strip().upper()


def lookup_coords(
    search: SearchEngine,
    city: str,
    state: str,
) -> Optional[Tuple[float, float]]:
    try:
        results: List[Any] = search.by_city_and_state(city=city, state=state)
    except ValueError:
        return None
    if not results:
        return None
    best = max(results, key=lambda z: z.population or 0)
    if best.lat is None or best.lng is None:
        return None
    return best.lat, best.lng


def iter_rows() -> Iterable[Dict[str, str]]:
    with RAW_CSV.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        for row in reader:
            yield row


def build_dataset() -> List[StationRecord]:
    DATA_DIR.mkdir(exist_ok=True)
    search = SearchEngine()
    city_cache: Dict[Tuple[str, str], Optional[Tuple[float, float]]] = {}
    records: List[StationRecord] = []
    dedupe: set[Tuple[str, str, str]] = set()

    try:
        for row in iter_rows():
            city = normalize_city(row["City"])
            state = normalize_state(row["State"])
            name = " ".join(row["Truckstop Name"].split())
            key = (name.lower(), city.lower(), state)
            if key in dedupe:
                continue
            dedupe.add(key)

            cache_key = (city, state)
            coords = city_cache.get(cache_key)
            if coords is None:
                coords = lookup_coords(search, city, state)
                city_cache[cache_key] = coords

            if coords is None:
                continue

            lat, lon = coords
            try:
                price = float(row["Retail Price"])
            except (TypeError, ValueError):
                continue

            records.append(
                StationRecord(
                    opis_id=row["OPIS Truckstop ID"],
                    name=name,
                    address=row["Address"].strip(),
                    city=city,
                    state=state,
                    rack_id=row["Rack ID"],
                    retail_price=price,
                    latitude=lat,
                    longitude=lon,
                )
            )
    finally:
        search.close()

    return records


def main() -> None:
    records = build_dataset()
    OUTPUT_JSON.write_text(
        json.dumps([asdict(record) for record in records], indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} station records to {OUTPUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

