from django.urls import path

from .import_views import ImportCommitView, ImportPreviewView
from .views import TransactionDetailView, TransactionListView

urlpatterns = [
    path("", TransactionListView.as_view(), name="transactions-list"),
    # Ahead of <holding_id>/<transaction_id>/ so "import" is never captured
    # as a holding_id.
    path("import/preview/", ImportPreviewView.as_view(), name="transactions-import-preview"),
    path("import/commit/", ImportCommitView.as_view(), name="transactions-import-commit"),
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
