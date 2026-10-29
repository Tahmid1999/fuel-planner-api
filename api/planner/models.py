import secrets

from django.db import models, transaction


class Country(models.Model):
    # Bangladesh sets one national price, so "cheapest stop" means nothing
    # there; the planner reads these fields instead of assuming the US.
    PER_STATION = "per_station"
    NATIONAL_FIXED = "national_fixed"

    code = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=60)
    currency = models.CharField(max_length=3)
    price_model = models.CharField(
        max_length=20,
        choices=[(PER_STATION, "Price per station"), (NATIONAL_FIXED, "One national price")],
    )
    distance_unit = models.CharField(max_length=2, choices=[("mi", "miles"), ("km", "km")])
    volume_unit = models.CharField(max_length=3, choices=[("gal", "gallons"), ("l", "litres")])

    class Meta:
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name


class City(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    state = models.CharField(max_length=40)
    lat = models.FloatField()
    lng = models.FloatField()
    population = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "cities"
        constraints = [
            models.UniqueConstraint(fields=["country", "name", "state"], name="city_unique")
        ]
        indexes = [models.Index(fields=["country", "name"])]

    def __str__(self):
        return self.label

    @property
    def label(self):
        return f"{self.name}, {self.state}"


class Station(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    opis_id = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=200)
    city = models.ForeignKey(City, on_delete=models.PROTECT)
    lat = models.FloatField()
    lng = models.FloatField()
    # The price file only names the town, so the position is the town's.
    location_precision = models.CharField(max_length=10, default="city")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["country", "opis_id"], name="station_unique")
        ]

    def __str__(self):
        return f"{self.name} ({self.city.label})"


class PriceList(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    source = models.CharField(max_length=120)
    as_of = models.DateField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.source}, {self.as_of}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.active:
                others = PriceList.objects.filter(country=self.country, active=True)
                others.exclude(pk=self.pk).update(active=False)
            super().save(*args, **kwargs)


class StationPrice(models.Model):
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="prices")
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["price_list", "station"], name="price_unique")
        ]


class RouteCache(models.Model):
    from_city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="+")
    to_city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="+")
    geometry = models.JSONField()  # [[lng, lat], ...]
    distance_mi = models.FloatField()
    duration_min = models.FloatField()
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_city", "to_city"], name="route_unique")
        ]


def new_plan_id():
    return secrets.token_urlsafe(9)


class TripPlan(models.Model):
    id = models.CharField(max_length=16, primary_key=True, default=new_plan_id, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # Old plans keep the prices they were made with.
    price_list = models.ForeignKey(PriceList, on_delete=models.PROTECT)
    from_city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="+")
    to_city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="+")
    inputs = models.JSONField()
    result = models.JSONField()
