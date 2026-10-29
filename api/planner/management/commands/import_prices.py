import datetime as dt

from django.core.management.base import BaseCommand

from planner.importers import import_prices
from planner.models import Country


class Command(BaseCommand):
    help = "Load an OPIS price CSV as a new price list (active unless --inactive)."

    def add_arguments(self, parser):
        parser.add_argument("csv")
        parser.add_argument("--source", required=True)
        parser.add_argument("--as-of", required=True, type=dt.date.fromisoformat)
        parser.add_argument("--country", default="US")
        parser.add_argument("--inactive", action="store_true")

    def handle(self, *args, **opts):
        country = Country.objects.get(code=opts["country"])
        with open(opts["csv"], encoding="utf-8-sig") as f:
            report = import_prices(
                f, country, opts["source"], opts["as_of"], activate=not opts["inactive"]
            )
        self.stdout.write(report.summary())
        for label in report.skipped_unknown_city:
            self.stdout.write(f"  no city: {label}")
