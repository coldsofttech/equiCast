from django.conf import settings
from equicast_core import (
    HoldingsClient,
    WatchlistLimitExceededError,
    WatchlistNotFoundError,
    WatchlistsClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Fields required to create a watchlist; description may be blank but must
#: be present so a caller doesn't silently omit it.
REQUIRED_CREATE_FIELDS = {"name", "description"}
UPDATABLE_FIELDS = {"name", "description"}

#: One shared client for the process, mirroring accounts/views.py's
#: module-level _client pattern.
_client = WatchlistsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_watchlists=settings.MAX_WATCHLISTS,
)
#: Needed to nest a watchlist's holdings under WatchlistDetailView.get and
#: to guard/force-delete them under WatchlistDetailView.delete —
#: holdings/views.py holds the client actually used for holdings CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)


class WatchlistListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(_client.list_watchlists(request.user.user_id))

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        try:
            watchlist = _client.create_watchlist(
                request.user.user_id,
                name=request.data["name"],
                description=request.data["description"],
            )
        except WatchlistLimitExceededError:
            # Static, caller-agnostic message — same py/stack-trace-exposure
            # reasoning as AccountListView.post's 409 (see accounts/views.py).
            detail = f"Watchlist limit reached (max {_client.max_watchlists})."
            return Response({"detail": detail}, status=409)
        return Response(watchlist, status=201)


class WatchlistDetailView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, watchlist_id: str) -> Response:
        try:
            watchlist = _client.get_watchlist(request.user.user_id, watchlist_id)
        except WatchlistNotFoundError:
            return Response(status=404)
        holdings = _holdings_client.list_holdings(request.user.user_id, watchlist_id=watchlist_id)
        return Response({**watchlist, "holdings": holdings})

    def patch(self, request: Request, watchlist_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            watchlist = _client.update_watchlist(request.user.user_id, watchlist_id, **fields)
        except WatchlistNotFoundError:
            return Response(status=404)
        return Response(watchlist)

    def delete(self, request: Request, watchlist_id: str) -> Response:
        force = request.query_params.get("force", "").lower() == "true"
        holdings = _holdings_client.list_holdings(request.user.user_id, watchlist_id=watchlist_id)
        if holdings and not force:
            return Response(
                {
                    "detail": "Watchlist has holdings; remove them first, "
                    "or retry with ?force=true to delete them along with the watchlist."
                },
                status=409,
            )

        try:
            if force and holdings:
                _holdings_client.delete_holdings_for_watchlist(request.user.user_id, watchlist_id)
            _client.delete_watchlist(request.user.user_id, watchlist_id)
        except WatchlistNotFoundError:
            return Response(status=404)
        return Response(status=204)
