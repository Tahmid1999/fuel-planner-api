import csv
import gzip

from django.core.management.base import BaseCommand

from planner.models import City


class Command(BaseCommand):
    help = "Write the US city table to a CSV (gzipped when the name ends in .gz) for seed_demo."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True)

    def handle(self, *args, **opts):
        path = opts["out"]
        opener = gzip.open if path.endswith(".gz") else open
        rows = City.objects.filter(country_id="US").order_by("state", "name")
        # newline="" or the csv module doubles line endings on Windows
        with opener(path, "wt", encoding="utf-8", newline="") as f:
            out = csv.writer(f, lineterminator="\n")
            out.writerow(["name", "state", "lat", "lng", "population"])
            for c in rows.iterator():
                out.writerow([c.name, c.state, round(c.lat, 5), round(c.lng, 5), c.population])
        self.stdout.write(f"{rows.count()} cities to {path}")
