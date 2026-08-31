from django.urls import path

from .views import PieDetailView, PieListView

urlpatterns = [
    path("", PieListView.as_view(), name="pies-list"),
    path("<str:pie_id>/", PieDetailView.as_view(), name="pies-detail"),
]
