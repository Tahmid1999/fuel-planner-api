import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-secret")
os.environ.setdefault("DJANGO_SECURE", "0")

from .settings import *  # noqa: E402, F403

# the manifest storage needs collectstatic first; tests don't run it
STATIC_ROOT = None
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
