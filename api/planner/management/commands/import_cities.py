from django.core.management.base import BaseCommand

from planner.importers import import_cities
from planner.models import Country


class Command(BaseCommand):
    help = "Build the US city table from uszipcode (downloads its database on first run)."

    def add_arguments(self, parser):
        parser.add_argument("--country", default="US")

    def handle(self, *args, **opts):
        count = import_cities(Country.objects.get(code=opts["country"]))
        self.stdout.write(f"{count} cities")
