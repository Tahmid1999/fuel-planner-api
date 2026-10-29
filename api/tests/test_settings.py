import os
import subprocess
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1]


def load_settings(**env):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("DJANGO_")}
    clean.update(env, DJANGO_SETTINGS_MODULE="fuelplanner.settings")
    code = "import django; django.setup(); from django.conf import settings; print(settings.DEBUG)"
    return subprocess.run(
        [sys.executable, "-c", code], cwd=API, env=clean, capture_output=True, text=True
    )


def test_production_without_secret_key_refuses_to_start():
    result = load_settings()
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_debug_runs_without_secret_key():
    assert load_settings(DJANGO_DEBUG="1").returncode == 0


def test_production_with_secret_key_starts():
    assert load_settings(DJANGO_SECRET_KEY="x" * 50).returncode == 0
