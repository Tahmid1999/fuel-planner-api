from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(help_text="Starting address (city, state).")
    finish = serializers.CharField(help_text="Destination address (city, state).")
    vehicle_range_miles = serializers.FloatField(
        min_value=100,
        max_value=800,
        required=False,
        default=500,
        help_text="Maximum miles the vehicle can travel on a full tank.",
    )
    fuel_efficiency_mpg = serializers.FloatField(
        min_value=5,
        max_value=60,
        required=False,
        default=10,
        help_text="Vehicle fuel efficiency in miles per gallon.",
    )

