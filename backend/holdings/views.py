from django.conf import settings
from equicast_core import (
    AccountsClient,
    HoldingAlreadyExistsError,
    HoldingLimitExceededError,
    HoldingNotFoundError,
    HoldingsClient,
    MarketDataClient,
    WatchlistsClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

ASSET_CLASSES = {"fx", "stock", "etf"}

#: Fields required to create a holding; account_id/watchlist_id aren't
#: listed here since exactly one of them is required instead — checked
#: separately below, same reasoning as pies/views.py leaving account_id
#: out of a plain required-fields set for a similar per-field rule.
REQUIRED_CREATE_FIELDS = {"ticker", "asset_class"}

#: One shared client for the process, mirroring pies/views.py's module-level
#: _client pattern.
_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
#: Needed only to validate a holding's account_id/watchlist_id belongs to
#: the caller — accounts/views.py and watchlists/views.py hold the clients
#: actually used for those domains' own CRUD.
_accounts_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)
_watchlists_client = WatchlistsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_watchlists=settings.MAX_WATCHLISTS,
)
#: Validates a holding's ticker actually has market data before it's
#: allowed to be created — same client market_data/views.py's ProfileView
#: uses.
_market_data_client = MarketDataClient(settings.MARKET_DATA_BUCKET, region_name=settings.AWS_REGION)


class HoldingListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        account_id = request.query_params.get("account_id")
        pie_id = request.query_params.get("pie_id")
        watchlist_id = request.query_params.get("watchlist_id")
        if sum(f is not None for f in (account_id, pie_id, watchlist_id)) > 1:
            return Response(
                {"detail": "At most one of account_id, pie_id, watchlist_id may be given."},
                status=400,
            )

        return Response(
            _client.list_holdings(
                request.user.user_id,
                account_id=account_id,
                pie_id=pie_id,
                watchlist_id=watchlist_id,
            )
        )

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        # A pie's holdings must always sum to exactly 100% allocation, which
        # a standalone single-item create can't maintain once the pie
        # already holds anything — sync_pie_holdings (PUT
        # /api/pies/<id>/holdings/) is the only way to add to a pie.
        if request.data.get("pie_id"):
            return Response(
                {"detail": "Pie-scoped holdings are created via PUT /api/pies/<id>/holdings/."},
                status=400,
            )

        account_id = request.data.get("account_id")
        watchlist_id = request.data.get("watchlist_id")
        if (account_id is None) == (watchlist_id is None):
            return Response(
                {"detail": "Exactly one of account_id, watchlist_id is required."}, status=400
            )

        asset_class = request.data["asset_class"]
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        if account_id is not None:
            caller_account_ids = {
                a["id"] for a in _accounts_client.list_accounts(request.user.user_id)
            }
            if account_id not in caller_account_ids:
                return Response({"detail": "Unknown account_id."}, status=400)
        else:
            caller_watchlist_ids = {
                w["id"] for w in _watchlists_client.list_watchlists(request.user.user_id)
            }
            if watchlist_id not in caller_watchlist_ids:
                return Response({"detail": "Unknown watchlist_id."}, status=400)

        ticker = request.data["ticker"].upper()
        if _market_data_client.get_profile(asset_class, ticker) is None:
            return Response({"detail": f"No {asset_class} data for '{ticker}'."}, status=400)

        try:
            holding = _client.create_holding(
                request.user.user_id,
                ticker=ticker,
                asset_class=asset_class,
                account_id=account_id,
                watchlist_id=watchlist_id,
            )
        except HoldingAlreadyExistsError:
            return Response({"detail": f"'{ticker}' is already held here."}, status=409)
        except HoldingLimitExceededError:
            # Static, caller-agnostic message — same py/stack-trace-exposure
            # reasoning as AccountListView.post's 409 (see accounts/views.py).
            cap = (
                _client.max_holdings_for_account
                if account_id is not None
                else _client.max_holdings_for_watchlist
            )
            return Response({"detail": f"Holding limit reached here (max {cap})."}, status=409)
        return Response(holding, status=201)


class HoldingDetailView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, holding_id: str) -> Response:
        try:
            holding = _client.get_holding(request.user.user_id, holding_id)
        except HoldingNotFoundError:
            return Response(status=404)
        return Response(holding)

    def delete(self, request: Request, holding_id: str) -> Response:
        try:
            _client.delete_holding(request.user.user_id, holding_id)
        except HoldingNotFoundError:
            return Response(status=404)
        except ValueError:
            return Response(
                {"detail": "Pie-scoped holdings are removed via PUT /api/pies/<id>/holdings/."},
                status=400,
            )
        return Response(status=204)
