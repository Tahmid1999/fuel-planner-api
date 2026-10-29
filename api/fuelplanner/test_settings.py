import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")

from .settings import *  # noqa: E402, F403
