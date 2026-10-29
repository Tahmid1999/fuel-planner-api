#!/bin/sh
set -e

# migrate, seeding and the worker setup are in gunicorn.conf.py
exec gunicorn fuelplanner.wsgi:application -c gunicorn.conf.py
