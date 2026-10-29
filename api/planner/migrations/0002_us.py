from django.db import migrations


def add_us(apps, schema_editor):
    Country = apps.get_model("planner", "Country")
    Country.objects.update_or_create(
        code="US",
        defaults={
            "name": "United States",
            "currency": "USD",
            "price_model": "per_station",
            "distance_unit": "mi",
            "volume_unit": "gal",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("planner", "0001_initial")]

    operations = [migrations.RunPython(add_us, migrations.RunPython.noop)]
