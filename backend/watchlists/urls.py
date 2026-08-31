from django.urls import path

from .views import WatchlistDetailView, WatchlistListView

urlpatterns = [
    path("", WatchlistListView.as_view(), name="watchlists-list"),
    path("<str:watchlist_id>/", WatchlistDetailView.as_view(), name="watchlists-detail"),
]
