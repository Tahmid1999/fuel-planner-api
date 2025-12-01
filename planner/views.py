from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RouteRequestSerializer
from .services import PlannerError, list_available_cities, plan_route


class RoutePlanView(APIView):
    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = plan_route(**serializer.validated_data)
        except PlannerError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload)


class RouteDemoView(TemplateView):
    template_name = "planner/demo.html"


class CityListView(APIView):
    def get(self, request):
        try:
            cities = list_available_cities()
        except PlannerError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"cities": cities})
