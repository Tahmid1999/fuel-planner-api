import math

from rest_framework import serializers

from . import defaults
from .models import City


class CitySerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = City
        fields = ["id", "name", "state", "label"]


class FiniteFloatField(serializers.FloatField):
    # FloatField takes "nan", and NaN passes every min/max check.
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            raise serializers.ValidationError("A valid number is required.")
        return value


class PlanRequestSerializer(serializers.Serializer):
    from_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.filter(country_id="US"))
    to_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.filter(country_id="US"))
    mpg = FiniteFloatField(min_value=3, max_value=15, default=defaults.MPG)
    tank_gal = FiniteFloatField(min_value=20, max_value=400, default=defaults.TANK_GAL)
    start_pct = FiniteFloatField(min_value=0, max_value=100, default=defaults.START_PCT)
    reserve_pct = FiniteFloatField(min_value=0, default=defaults.RESERVE_PCT)
    max_detour_mi = FiniteFloatField(min_value=0, max_value=10, default=defaults.MAX_DETOUR_MI)

    def validate_reserve_pct(self, value):
        if value >= 50:
            raise serializers.ValidationError("Must be less than 50.")
        return value

    def validate(self, data):
        if data["from_city"] == data["to_city"]:
            raise serializers.ValidationError({"to_city": "Pick a different city from the start."})
        if data["start_pct"] <= data["reserve_pct"]:
            raise serializers.ValidationError(
                {"start_pct": "The tank has to start above the reserve."}
            )
        # Detour is only a filter, so the plan can reach an exit with just the
        # reserve left; the reserve has to cover the trip off the road and back.
        reserve_gal = data["tank_gal"] * data["reserve_pct"] / 100
        detour_gal = 2 * data["max_detour_mi"] / data["mpg"]
        if reserve_gal < detour_gal:
            raise serializers.ValidationError(
                {
                    "reserve_pct": f"Too small for a {data['max_detour_mi']:g} mile detour: "
                    f"keep at least {detour_gal:.1f} gallons."
                }
            )
        return data

    def inputs(self):
        names = ["mpg", "tank_gal", "start_pct", "reserve_pct", "max_detour_mi"]
        return {name: float(self.validated_data[name]) for name in names}


# The classes below only describe responses for the OpenAPI schema; the views
# build the dicts themselves (see trips.plan_document).


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ActivePricesSerializer(serializers.Serializer):
    source = serializers.CharField()
    as_of = serializers.DateField()
    station_count = serializers.IntegerField()


class PlaceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class StopSerializer(serializers.Serializer):
    opis_id = serializers.CharField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    mile = serializers.FloatField()
    detour_mi = serializers.FloatField(help_text="Off the route, one way.")
    detour_gal = serializers.FloatField(help_text="Fuel for the detour there and back.")
    price = serializers.FloatField()
    gallons = serializers.FloatField()
    cost = serializers.FloatField()


class PlanPartSerializer(serializers.Serializer):
    stops = StopSerializer(many=True)
    spend = serializers.FloatField()
    leftover_value = serializers.FloatField(help_text="What the fuel left on arrival cost.")
    cost = serializers.FloatField(help_text="spend - leftover_value")
    gallons = serializers.FloatField()


class RouteSerializer(serializers.Serializer):
    distance_mi = serializers.FloatField()
    duration_min = serializers.IntegerField()
    geometry = serializers.JSONField(help_text="GeoJSON LineString, [lng, lat] pairs.")


class PricesUsedSerializer(serializers.Serializer):
    source = serializers.CharField()
    as_of = serializers.DateField()


class InputsSerializer(serializers.Serializer):
    mpg = FiniteFloatField()
    tank_gal = FiniteFloatField()
    start_pct = FiniteFloatField()
    reserve_pct = FiniteFloatField()
    max_detour_mi = FiniteFloatField()


class PlanDocumentSerializer(serializers.Serializer):
    id = serializers.CharField()
    created_at = serializers.DateTimeField()
    from_ = PlaceSerializer()
    to = PlaceSerializer()
    inputs = InputsSerializer()
    prices = PricesUsedSerializer()
    route = RouteSerializer()
    plan = PlanPartSerializer(help_text="The cheapest plan.")
    baseline = PlanPartSerializer(help_text="Fill to full when a leg would leave under 25%.")
    savings = serializers.FloatField(help_text="baseline.cost - plan.cost")

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields
