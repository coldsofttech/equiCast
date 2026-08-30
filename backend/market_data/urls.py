from django.urls import path

from .views import PricesView, ProfileView

urlpatterns = [
    path("<str:asset_class>/<str:symbol>/profile/", ProfileView.as_view(), name="profile"),
    path("<str:asset_class>/<str:symbol>/prices/", PricesView.as_view(), name="prices"),
]
