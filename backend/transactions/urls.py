from django.urls import path

from .views import TransactionDetailView, TransactionListView

urlpatterns = [
    path("", TransactionListView.as_view(), name="transactions-list"),
    # Nested under holding_id, not a flat <transaction_id>/ — transactions
    # are stored one JSON object per holding (see TransactionsClient), so
    # an id-only lookup would otherwise have to scan every holding file for
    # the user. The caller always has holding_id in hand here: transactions
    # are only ever shown scoped to a holding (?holding_id= on the list
    # endpoint, or the holding's own detail view).
    path(
        "<str:holding_id>/<str:transaction_id>/",
        TransactionDetailView.as_view(),
        name="transactions-detail",
    ),
]
