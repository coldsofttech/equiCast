from django.urls import path

from .views import PieDetailView, PieHoldingsView, PieListView

urlpatterns = [
    path("", PieListView.as_view(), name="pies-list"),
    path("<str:pie_id>/", PieDetailView.as_view(), name="pies-detail"),
    path("<str:pie_id>/holdings/", PieHoldingsView.as_view(), name="pies-holdings"),
]
