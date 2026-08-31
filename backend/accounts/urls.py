from django.urls import path

from .views import AccountDetailView, AccountListView

urlpatterns = [
    path("", AccountListView.as_view(), name="accounts-list"),
    path("<str:account_id>/", AccountDetailView.as_view(), name="accounts-detail"),
]
