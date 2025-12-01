#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

SUPPORTED_MAJOR = 3
MINOR_RANGE = (12, 13)  # [12, 13)


def ensure_supported_python() -> None:
    if not (sys.version_info.major == SUPPORTED_MAJOR and MINOR_RANGE[0] <= sys.version_info.minor < MINOR_RANGE[1]):
        ver = ".".join(map(str, sys.version_info[:3]))
        raise RuntimeError(
            f"FuelPlanner requires Python {SUPPORTED_MAJOR}.{MINOR_RANGE[0]}.*; detected {ver}. "
            "Create the virtual environment with Python 3.12 as documented in README.md."
        )


def main():
    """Run administrative tasks."""
    ensure_supported_python()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fuelplanner.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
