from django.urls import path

from .views import (
    DividendsView,
    EventsView,
    FxRateView,
    MetricsView,
    NewsView,
    PricesView,
    ProfileView,
    SearchView,
)

urlpatterns = [
    path("search/", SearchView.as_view(), name="search"),
    path("fx-rate/<str:from_currency>/<str:to_currency>/", FxRateView.as_view(), name="fx-rate"),
    path("<str:asset_class>/<str:symbol>/profile/", ProfileView.as_view(), name="profile"),
    path("<str:asset_class>/<str:symbol>/prices/", PricesView.as_view(), name="prices"),
    path("<str:asset_class>/<str:symbol>/metrics/", MetricsView.as_view(), name="metrics"),
    path("<str:asset_class>/<str:symbol>/dividends/", DividendsView.as_view(), name="dividends"),
    path("<str:asset_class>/<str:symbol>/news/", NewsView.as_view(), name="news"),
    path("<str:asset_class>/<str:symbol>/events/", EventsView.as_view(), name="events"),
]
