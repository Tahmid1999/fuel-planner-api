from rest_framework import serializers

from . import defaults
from .models import City


class CitySerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = City
        fields = ["id", "name", "state", "label"]


class PlanRequestSerializer(serializers.Serializer):
    from_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.filter(country_id="US"))
    to_city = serializers.PrimaryKeyRelatedField(queryset=City.objects.filter(country_id="US"))
    mpg = serializers.FloatField(min_value=3, max_value=15, default=defaults.MPG)
    tank_gal = serializers.FloatField(min_value=20, max_value=400, default=defaults.TANK_GAL)
    start_pct = serializers.FloatField(min_value=0, max_value=100, default=defaults.START_PCT)
    reserve_pct = serializers.FloatField(min_value=0, default=defaults.RESERVE_PCT)
    max_detour_mi = serializers.FloatField(
        min_value=0, max_value=10, default=defaults.MAX_DETOUR_MI
    )

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
        return data

    def inputs(self):
        names = ["mpg", "tank_gal", "start_pct", "reserve_pct", "max_detour_mi"]
        return {name: float(self.validated_data[name]) for name in names}
