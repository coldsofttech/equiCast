from django.urls import path

from .views import TickerHistoryView

urlpatterns = [
    path("<str:ticker>/", TickerHistoryView.as_view(), name="ticker-history"),
]
