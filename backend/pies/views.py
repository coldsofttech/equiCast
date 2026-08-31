from django.conf import settings
from equicast_core import (
    AccountsClient,
    AllocationError,
    HoldingAlreadyExistsError,
    HoldingLimitExceededError,
    HoldingNotFoundError,
    HoldingsClient,
    MarketDataClient,
    PieLimitExceededError,
    PieNotFoundError,
    PiesClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Fields required to create a pie; description may be blank but must be
#: present so a caller doesn't silently omit it.
REQUIRED_CREATE_FIELDS = {"name", "description", "account_id"}
#: account_id is intentionally excluded — a pie doesn't move between
#: accounts, so it's immutable after creation.
UPDATABLE_FIELDS = {"name", "description"}

#: One shared client for the process, mirroring accounts/views.py's
#: module-level _client pattern.
_client = PiesClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_pies_per_account=settings.MAX_PIES,
)
#: Needed only to validate a pie's account_id belongs to the caller —
#: accounts/views.py holds the client actually used for accounts CRUD.
_accounts_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)
#: Needed to nest a pie's holdings under PieDetailView.get, guard/force-
#: delete them under PieDetailView.delete, and back PieHoldingsView's
#: add/remove/reallocate batch — holdings/views.py holds the client actually
#: used for account-direct/watchlist holdings CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
#: Validates an added holding's ticker actually has market data before it's
#: allowed into a pie — same client market_data/views.py's ProfileView and
#: holdings/views.py use.
_market_data_client = MarketDataClient(settings.MARKET_DATA_BUCKET, region_name=settings.AWS_REGION)


class PieListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        account_id = request.query_params.get("account_id")
        return Response(_client.list_pies(request.user.user_id, account_id=account_id))

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        account_id = request.data["account_id"]
        caller_account_ids = {a["id"] for a in _accounts_client.list_accounts(request.user.user_id)}
        if account_id not in caller_account_ids:
            return Response({"detail": "Unknown account_id."}, status=400)

        try:
            pie = _client.create_pie(
                request.user.user_id,
                account_id=account_id,
                name=request.data["name"],
                description=request.data["description"],
            )
        except PieLimitExceededError:
            # Static, caller-agnostic message — same py/stack-trace-exposure
            # reasoning as AccountListView.post's 409 (see accounts/views.py).
            detail = f"Pie limit reached for this account (max {_client.max_pies_per_account})."
            return Response({"detail": detail}, status=409)
        return Response(pie, status=201)


class PieDetailView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pie_id: str) -> Response:
        try:
            pie = _client.get_pie(request.user.user_id, pie_id)
        except PieNotFoundError:
            return Response(status=404)
        holdings = _holdings_client.list_holdings(request.user.user_id, pie_id=pie_id)
        return Response({**pie, "holdings": holdings})

    def patch(self, request: Request, pie_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            pie = _client.update_pie(request.user.user_id, pie_id, **fields)
        except PieNotFoundError:
            return Response(status=404)
        return Response(pie)

    def delete(self, request: Request, pie_id: str) -> Response:
        force = request.query_params.get("force", "").lower() == "true"
        holdings = _holdings_client.list_holdings(request.user.user_id, pie_id=pie_id)
        if holdings and not force:
            return Response(
                {
                    "detail": "Pie has holdings; remove them first, "
                    "or retry with ?force=true to delete them along with the pie."
                },
                status=409,
            )

        try:
            if force and holdings:
                _holdings_client.delete_holdings_for_pies(request.user.user_id, [pie_id])
            _client.delete_pie(request.user.user_id, pie_id)
        except PieNotFoundError:
            return Response(status=404)
        return Response(status=204)


class PieHoldingsView(APIView):
    """Adds/removes/reallocates a pie's holdings in one atomic batch — the
    only way to mutate a pie's holdings, since a standalone single-item
    create/delete can't keep a pie's allocation_pct summing to exactly
    100%. See `HoldingsClient.sync_pie_holdings`."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request: Request, pie_id: str) -> Response:
        try:
            pie = _client.get_pie(request.user.user_id, pie_id)
        except PieNotFoundError:
            return Response(status=404)

        add = request.data.get("add", [])
        remove = request.data.get("remove", [])
        reallocate = request.data.get("reallocate", [])

        for entry in add:
            asset_class = entry.get("asset_class")
            if asset_class not in {"fx", "stock", "etf"}:
                return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)
            ticker = str(entry.get("ticker", "")).upper()
            entry["ticker"] = ticker
            if _market_data_client.get_profile(asset_class, ticker) is None:
                return Response({"detail": f"No {asset_class} data for '{ticker}'."}, status=400)

        try:
            holdings = _holdings_client.sync_pie_holdings(
                request.user.user_id, pie_id, add=add, remove=remove, reallocate=reallocate
            )
        except HoldingNotFoundError:
            return Response(
                {"detail": "remove/reallocate referenced an unknown holding id."}, status=400
            )
        except HoldingAlreadyExistsError as exc:
            return Response({"detail": str(exc)}, status=409)
        except HoldingLimitExceededError:
            cap = _holdings_client.max_holdings_for_pie
            return Response({"detail": f"Pie holding limit reached (max {cap})."}, status=409)
        except AllocationError as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response({**pie, "holdings": holdings})
