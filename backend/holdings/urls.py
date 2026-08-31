from django.urls import path

from .views import HoldingDetailView, HoldingListView

urlpatterns = [
    path("", HoldingListView.as_view(), name="holdings-list"),
    path("<str:holding_id>/", HoldingDetailView.as_view(), name="holdings-detail"),
]
