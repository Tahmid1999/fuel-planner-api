import datetime as dt
import gzip

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from planner.importers import active_price_list, import_prices, load_cities_csv
from planner.models import Country


class Command(BaseCommand):
    help = "Load the shipped US cities and the OPIS sample into an empty database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="do nothing when a price list is already active (runs at every container start)",
        )

    def handle(self, *args, **opts):
        if opts["if_empty"] and active_price_list("US"):
            self.stdout.write("already seeded")
            return

        us = Country.objects.get(code="US")
        cities_path = str(settings.SEED_CITIES)
        opener = gzip.open if cities_path.endswith(".gz") else open
        # one transaction: a restart halfway leaves nothing, and the next start
        # simply seeds again
        with transaction.atomic():
            with opener(cities_path, "rt", encoding="utf-8") as f:
                cities = load_cities_csv(f, us)
            with open(settings.SEED_PRICES, "rb") as f:
                report = import_prices(f, us, "OPIS sample", dt.date(2025, 11, 28))
        self.stdout.write(f"{cities} cities")
        self.stdout.write(report.summary())
