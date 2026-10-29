#!/bin/sh
set -e

python manage.py prepare_db
# 2 workers fit in 512 MB; 60 s covers a 20 s routing call plus the plan
exec gunicorn fuelplanner.wsgi:application   --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60 --access-logfile -
