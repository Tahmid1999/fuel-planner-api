from django.urls import path

from . import views

urlpatterns = [
    path("live/", views.LiveView.as_view(), name="live"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("cities/", views.CitySearchView.as_view(), name="city-search"),
    path("prices/active/", views.ActivePricesView.as_view(), name="active-prices"),
    path("plans/", views.PlanCreateView.as_view(), name="plan-create"),
    path("plans/<str:plan_id>/", views.PlanDetailView.as_view(), name="plan-detail"),
]
