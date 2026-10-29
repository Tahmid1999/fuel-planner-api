from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .fuel import Unreachable
from .importers import active_price_list
from .models import City, TripPlan
from .routing import RoutingUnavailable
from .serializers import CitySerializer, PlanRequestSerializer
from .trips import NoPrices, make_plan, plan_document

NO_PRICES = {"detail": "no prices loaded"}


class CitySearchView(APIView):
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])
        cities = City.objects.filter(country_id="US", name__istartswith=q).order_by(
            "-population", "name"
        )[:10]
        return Response(CitySerializer(cities, many=True).data)


class ActivePricesView(APIView):
    def get(self, request):
        price_list = active_price_list("US")
        if price_list is None:
            return Response(NO_PRICES, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {
                "source": price_list.source,
                "as_of": price_list.as_of.isoformat(),
                "station_count": price_list.prices.count(),
            }
        )


class PlanCreateView(APIView):
    def post(self, request):
        form = PlanRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        try:
            trip = make_plan(data["from_city"], data["to_city"], form.inputs())
        except Unreachable as exc:
            gap = exc.to_mile - exc.from_mile
            detail = (
                f"no fuel stop within range between mile {exc.from_mile:.1f} "
                f"and mile {exc.to_mile:.1f} ({gap:.1f} mi)"
            )
            return Response({"detail": detail}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except RoutingUnavailable:
            return Response(
                {"detail": "routing service unavailable, try again shortly"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except NoPrices:
            return Response(NO_PRICES, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            plan_document(trip),
            status=status.HTTP_201_CREATED,
            headers={"Location": f"/api/plans/{trip.id}/"},
        )


class PlanDetailView(APIView):
    def get(self, request, plan_id):
        trip = get_object_or_404(
            TripPlan.objects.select_related("from_city", "to_city"), pk=plan_id
        )
        return Response(plan_document(trip))
