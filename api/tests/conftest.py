import pytest

from planner.models import City, Country

CITIES = [
    ("Big Cabin", "OK"),
    ("Tomah", "WI"),
    ("Gila Bend", "AZ"),
    ("Fort Smith", "AR"),
    ("Columbia", "NJ"),
    ("Mount Jackson", "VA"),
    ("Jarrell", "TX"),
]


@pytest.fixture
def us():
    country = Country.objects.get(code="US")
    for i, (name, state) in enumerate(CITIES):
        City.objects.create(country=country, name=name, state=state, lat=30 + i, lng=-90 - i)
    return country
