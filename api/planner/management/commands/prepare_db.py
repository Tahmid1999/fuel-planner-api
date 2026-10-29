from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import OperationalError


class Command(BaseCommand):
    help = "Migrate and seed an empty database; never fails, so the server always starts."

    def handle(self, *args, **opts):
        # One process instead of two manage.py runs: Django boots once, which
        # matters on a free instance that runs this every time it wakes up.
        try:
            call_command("migrate", interactive=False, verbosity=0)
            call_command("seed_demo", if_empty=True, stdout=self.stdout)
        except OperationalError as exc:
            # Neon asleep, out of quota or unreachable: start anyway and answer
            # 503 until it's back, instead of exiting and being restarted
            self.stdout.write(f"database not reachable at start, serving 503s: {exc}")
