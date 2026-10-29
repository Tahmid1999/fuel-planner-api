#!/bin/sh
set -e

python manage.py migrate --noinput
# Render's free plan has no shell, so a new database fills itself here; every
# later start finds the price list and skips it.
python manage.py seed_demo --if-empty
# 2 workers fit in 512 MB; 60 s covers a 20 s routing call plus the plan
exec gunicorn fuelplanner.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60 --access-logfile -
