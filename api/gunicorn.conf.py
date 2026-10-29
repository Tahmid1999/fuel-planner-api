import os

from django.core.management import call_command
from django.db import connections
from django.urls import get_resolver

# A free instance has a tenth of a CPU core, where booting Django takes about
# 14 s. Load it once in the master and fork one worker from it, instead of a
# separate migrate run plus a fresh import in every worker (~40 s per wake-up).
preload_app = True
workers = 1
threads = 4
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
# covers a 20 s routing call plus the plan
timeout = 60
accesslog = "-"


def on_starting(server):
    call_command("prepare_db")
    # import the views here too, or the first request after a wake pays for it
    get_resolver().resolve("/api/plans/")
    # a connection opened in the master would be shared by the forked worker
    connections.close_all()
