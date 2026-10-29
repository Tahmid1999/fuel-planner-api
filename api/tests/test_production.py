import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.db import OperationalError
from django.test import override_settings

from planner import trips
from planner.models import City, Country

API = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.django_db


def test_health_ok(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "db": True}


def test_health_db_down_is_503(client, monkeypatch):
    def down():
        raise OperationalError("could not connect to server")

    monkeypatch.setattr("planner.views.connection.cursor", down)
    response = client.get("/api/health/")
    assert response.status_code == 503
    assert response.json() == {"ok": False, "db": False}


def test_plan_with_db_down_is_503(client, monkeypatch):
    us = Country.objects.get(code="US")
    a = City.objects.create(country=us, name="A", state="KS", lat=40, lng=-100)
    b = City.objects.create(country=us, name="B", state="KS", lat=40, lng=-96)

    def down(code):
        raise OperationalError("terminating connection due to administrator command")

    monkeypatch.setattr(trips, "active_price_list", down)
    response = client.post(
        "/api/plans/", {"from_city": a.id, "to_city": b.id}, content_type="application/json"
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable, try again shortly"}


@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^api/health/$"])
def test_health_not_redirected_in_production(client):
    # Render's health check and wake-up request come in over plain http
    assert client.get("/api/health/").status_code == 200
    assert client.get("/api/prices/active/").status_code == 301


def settings_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "ALLOWED_"))}
    env.update(DJANGO_SETTINGS_MODULE="fuelplanner.settings", **extra)
    return env


def test_deploy_check_is_clean():
    env = settings_env(
        DJANGO_SECRET_KEY=secrets.token_urlsafe(50),
        ALLOWED_HOSTS="example.onrender.com",
        CSRF_TRUSTED_ORIGINS="https://example.onrender.com",
    )
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=API,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_secure_off_allows_plain_http():
    code = (
        "import django; django.setup(); from django.conf import settings; "
        "print(settings.SECURE_SSL_REDIRECT)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=API,
        env=settings_env(DJANGO_SECRET_KEY="x" * 50, DJANGO_SECURE="0"),
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False", result.stderr


def test_render_hostname_is_trusted():
    # Render sets this on every web service; no hand-copied host needed
    code = (
        "import django; django.setup(); from django.conf import settings; "
        "print(settings.ALLOWED_HOSTS, settings.CSRF_TRUSTED_ORIGINS)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=API,
        env=settings_env(
            DJANGO_SECRET_KEY="x" * 50, RENDER_EXTERNAL_HOSTNAME="fuel-planner-api.onrender.com"
        ),
        capture_output=True,
        text=True,
    )
    assert "'fuel-planner-api.onrender.com'" in result.stdout, result.stderr
    assert "'https://fuel-planner-api.onrender.com'" in result.stdout
