from django.urls import path

from .views import CityListView, RouteDemoView, RoutePlanView

urlpatterns = [
    path("route-plan/", RoutePlanView.as_view(), name="route-plan"),
    path("demo/", RouteDemoView.as_view(), name="route-demo"),
    path("cities/", CityListView.as_view(), name="city-list"),
]
