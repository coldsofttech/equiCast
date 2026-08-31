from typing import Any

from django.conf import settings
from equicast_core import (
    AccountNotFoundError,
    AccountsClient,
    HoldingNotFoundError,
    HoldingsClient,
    InsufficientSharesError,
    PieNotFoundError,
    PiesClient,
    TransactionAlreadyExistsError,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
    TransactionsClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Asset classes transactions are allowed against — fx holdings never carry
#: transactions (see module docstring in equicast_core.transactions).
TRANSACTABLE_ASSET_CLASSES = {"stock", "etf"}

#: Valid values for a TRANSACTION-mode record's `type`, re-exported here so
#: holdings/views.py's embedded-transaction path can reuse the same set
#: without importing straight from equicast_core.transactions.
TRANSACTION_ACTIONS = {"BUY", "SELL"}

#: Field shape required/disallowed per account transaction_type — see
#: `build_transaction_fields`.
_FIELDS_BY_MODE = {
    "AVERAGE": {
        "required": {"no_of_shares", "average_price"},
        "disallowed": {"date", "type", "price"},
    },
    "TRANSACTION": {
        "required": {"no_of_shares", "price", "date", "type"},
        "disallowed": {"average_price"},
    },
}

UPDATABLE_FIELDS = {"no_of_shares", "average_price"}

#: One shared client for the process, mirroring holdings/views.py's
#: module-level _client pattern.
_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)
#: Needed only to look up a transaction's holding (and, via it, resolve the
#: owning account's transaction_type) — holdings/views.py holds the client
#: actually used for holdings CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
#: Needed only to walk a pie-scoped holding up to its owning account —
#: pies/views.py holds the client actually used for pies CRUD.
_pies_client = PiesClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_pies_per_account=settings.MAX_PIES,
)
#: Needed only to read the owning account's transaction_type — accounts/
#: views.py holds the client actually used for accounts CRUD.
_accounts_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)


def resolve_transaction_mode(
    user_id: str, holding: dict[str, Any]
) -> tuple[str | None, Response | None]:
    """Return `(transaction_type, None)` for `holding`'s owning account, or
    `(None, error_response)` if this holding isn't eligible for
    transactions at all. Shared by `TransactionListView.post` and
    holdings/views.py's embedded-transaction path on holding creation, so
    both apply the exact same eligibility/lookup rules."""
    if holding["watchlist_id"] is not None:
        return None, Response(
            {"detail": "Transactions aren't supported for watchlist holdings."}, status=400
        )
    if holding["asset_class"] not in TRANSACTABLE_ASSET_CLASSES:
        return None, Response(
            {"detail": "Transactions aren't supported for fx holdings."}, status=400
        )

    if holding["account_id"] is not None:
        account_id = holding["account_id"]
    else:
        try:
            pie = _pies_client.get_pie(user_id, holding["pie_id"])
        except PieNotFoundError:
            return None, Response({"detail": "Holding's pie no longer exists."}, status=400)
        account_id = pie["account_id"]

    try:
        account = _accounts_client.get_account(user_id, account_id)
    except AccountNotFoundError:
        return None, Response({"detail": "Holding's account no longer exists."}, status=400)
    return account["transaction_type"], None


def build_transaction_fields(
    data: dict[str, Any], mode: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate `data` against the field shape required for `mode`
    (`"AVERAGE"` or `"TRANSACTION"`), returning `(kwargs, None)` ready for
    `TransactionsClient.create_transaction`, or `(None, error_detail)` if
    the shape doesn't match. Shared the same way `resolve_transaction_mode`
    is."""
    shape = _FIELDS_BY_MODE[mode]
    missing = shape["required"] - data.keys()
    if missing:
        return None, f"Missing field(s) for {mode} mode: {', '.join(sorted(missing))}."
    present_disallowed = shape["disallowed"] & data.keys()
    if present_disallowed:
        return None, (
            f"Field(s) not applicable in {mode} mode: {', '.join(sorted(present_disallowed))}."
        )
    if mode == "TRANSACTION" and data["type"] not in TRANSACTION_ACTIONS:
        return None, f"Invalid type '{data['type']}'."

    return {
        "no_of_shares": data["no_of_shares"],
        "average_price": data.get("average_price"),
        "price": data.get("price"),
        "date": data.get("date"),
        "type": data.get("type"),
    }, None


class TransactionListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        holding_id = request.query_params.get("holding_id")
        year = request.query_params.get("year")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        return Response(
            _client.list_transactions(
                request.user.user_id,
                holding_id=holding_id,
                year=year,
                date_from=date_from,
                date_to=date_to,
            )
        )

    def post(self, request: Request) -> Response:
        holding_id = request.data.get("holding_id")
        if not holding_id:
            return Response({"detail": "Missing field(s): holding_id."}, status=400)

        try:
            holding = _holdings_client.get_holding(request.user.user_id, holding_id)
        except HoldingNotFoundError:
            return Response({"detail": "Unknown holding_id."}, status=400)

        mode, error = resolve_transaction_mode(request.user.user_id, holding)
        if error is not None:
            return error
        assert mode is not None

        fields, detail = build_transaction_fields(request.data, mode)
        if detail is not None:
            return Response({"detail": detail}, status=400)
        assert fields is not None

        try:
            transaction = _client.create_transaction(
                request.user.user_id, holding_id, mode, **fields
            )
        except TransactionAmountError:
            return Response(
                {
                    "detail": "no_of_shares/average_price/price must be positive numbers, "
                    "and type must be BUY or SELL."
                },
                status=400,
            )
        except TransactionAlreadyExistsError:
            # Static, caller-agnostic message rather than str(exc) — same
            # py/stack-trace-exposure reasoning as PieHoldingsView.put's 409
            # (see pies/views.py).
            return Response(
                {"detail": "Holding already has an AVERAGE record — update it instead."},
                status=409,
            )
        except TransactionLimitExceededError:
            cap = _client.max_transactions_for_holding
            return Response(
                {"detail": f"Transaction limit reached for this holding (max {cap})."}, status=409
            )
        except InsufficientSharesError:
            return Response(
                {"detail": "Sell quantity exceeds net shares recorded for this holding."},
                status=409,
            )
        return Response(transaction, status=201)


class TransactionDetailView(APIView):
    """Addressed by `holding_id`/`transaction_id` together, not
    `transaction_id` alone — transactions are stored one JSON object per
    holding (see `TransactionsClient`), so this is a single-file
    read/write rather than a scan across every holding the user has."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, holding_id: str, transaction_id: str) -> Response:
        try:
            transaction = _client.get_transaction(request.user.user_id, holding_id, transaction_id)
        except TransactionNotFoundError:
            return Response(status=404)
        return Response(transaction)

    def patch(self, request: Request, holding_id: str, transaction_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            transaction = _client.update_transaction(
                request.user.user_id, holding_id, transaction_id, **fields
            )
        except TransactionNotFoundError:
            return Response(status=404)
        except TransactionAmountError:
            return Response(
                {"detail": "no_of_shares/average_price must be positive numbers."}, status=400
            )
        except ValueError:
            return Response(
                {"detail": "TRANSACTION-mode records are immutable — create a new one instead."},
                status=400,
            )
        return Response(transaction)

    def delete(self, request: Request, holding_id: str, transaction_id: str) -> Response:
        try:
            _client.delete_transaction(request.user.user_id, holding_id, transaction_id)
        except TransactionNotFoundError:
            return Response(status=404)
        return Response(status=204)
