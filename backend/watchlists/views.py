from typing import Any

from django.conf import settings
from equicast_core import (
    HoldingsClient,
    MarketDataClient,
    UserProfileClient,
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

#: The five system-default watchlists every user sees, in display order.
#: Unlike a custom watchlist, these aren't stored in S3 at all (see
#: WatchlistsClient's docstring — that store only ever holds user-created
#: ones) — just a fixed list merged into WatchlistListView.get's response
#: alongside the caller's own custom watchlists, each tagged "type": "system"
#: there.
SYSTEM_WATCHLISTS: list[dict[str, Any]] = [
    {"id": "global-markets", "name": "Global Markets"},
    {"id": "top-winners", "name": "Top Winners"},
    {"id": "top-losers", "name": "Top Losers"},
    {"id": "top-winners-accounts", "name": "Top Winners (Your Accounts)"},
    {"id": "top-losers-accounts", "name": "Top Losers (Your Accounts)"},
]

#: Maps a system watchlist's `id` to the S3 partition key `equicast-watchlist`
#: publishes it under (`watchlist=<KEY>/entries.parquet` — see
#: MarketDataClient.get_watchlist_entries and packages/watchlist/README.md).
#: Deliberately a separate lookup from SYSTEM_WATCHLISTS itself rather than
#: a third field on each entry there, so `**w` below only ever echoes
#: display fields (id/name) to the frontend, never this internal wiring
#: detail. A system watchlist with no entry here (every one but Global
#: Markets, for now) always comes back with `holdings: []` — how each of
#: those gets populated (global market movers, the caller's own accounts'
#: movers, …) is deliberately separate, not-yet-built work.
_SYSTEM_WATCHLIST_STORAGE_KEYS: dict[str, str] = {
    "global-markets": "GLOBAL_MARKETS",
}

#: One shared client for the process, mirroring accounts/views.py's
#: module-level _client pattern.
_client = WatchlistsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_watchlists=settings.MAX_WATCHLISTS,
)
#: Needed to nest a watchlist's holdings under WatchlistListView.get/
#: WatchlistDetailView.get and to guard/force-delete them under
#: WatchlistDetailView.delete — holdings/views.py holds the client actually
#: used for holdings CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
#: Needed to merge each holding's current_price_native/current_price (and
#: name/sector/industry/website) in via `enrich_holdings` — pies/views.py
#: holds the client instance actually used to validate a ticker has market
#: data before it's added to a pie.
_market_data_client = MarketDataClient(settings.MARKET_DATA_BUCKET, region_name=settings.AWS_REGION)
#: Needed only to read the user's default_currency, so `enrich_holdings`
#: converts current_price the same way accounts/views.py's and
#: pies/views.py's own `_enrich_holdings` do — identity/views.py holds the
#: client actually used for profile CRUD.
_profile_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)


def _enrich_holdings(user_id: str, holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same enrichment as accounts/views.py's and pies/views.py's own
    `_enrich_holdings` — see either's docstring for what it fills in and
    why. Duplicated rather than shared since those two already each carry
    their own copy rather than a common helper."""
    if not holdings:
        return holdings
    default_currency = _profile_client.get_or_create_profile(user_id)["default_currency"]
    return _market_data_client.enrich_holdings(holdings, default_currency)


class WatchlistListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user_id = request.user.user_id
        watchlists = _client.list_watchlists(user_id)

        watchlist_ids = {w["id"] for w in watchlists}
        holdings = [
            h for h in _holdings_client.list_holdings(user_id) if h["watchlist_id"] in watchlist_ids
        ]
        holdings_by_watchlist: dict[str, list[dict[str, Any]]] = {}
        for holding in _enrich_holdings(user_id, holdings):
            holdings_by_watchlist.setdefault(holding["watchlist_id"], []).append(holding)

        system = [
            {
                **w,
                "type": "system",
                "holdings": (
                    _market_data_client.get_watchlist_entries(storage_key)
                    if (storage_key := _SYSTEM_WATCHLIST_STORAGE_KEYS.get(w["id"]))
                    else []
                ),
            }
            for w in SYSTEM_WATCHLISTS
        ]
        custom = [
            {**w, "type": "custom", "holdings": holdings_by_watchlist.get(w["id"], [])}
            for w in watchlists
        ]
        return Response([*system, *custom])

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
        return Response({**watchlist, "type": "custom", "holdings": []}, status=201)


class WatchlistDetailView(APIView):
    """Custom watchlists only — a system watchlist (see SYSTEM_WATCHLISTS)
    has no S3-backed row for `_client` to look up, and isn't linked from the
    frontend's tabbed panel anyway (WatchlistListView.get's response already
    carries everything each tab needs, system or custom alike)."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, watchlist_id: str) -> Response:
        try:
            watchlist = _client.get_watchlist(request.user.user_id, watchlist_id)
        except WatchlistNotFoundError:
            return Response(status=404)
        holdings = _holdings_client.list_holdings(request.user.user_id, watchlist_id=watchlist_id)
        return Response(
            {**watchlist, "type": "custom", "holdings": _enrich_holdings(request.user.user_id, holdings)}
        )

    def patch(self, request: Request, watchlist_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            watchlist = _client.update_watchlist(request.user.user_id, watchlist_id, **fields)
        except WatchlistNotFoundError:
            return Response(status=404)
        return Response({**watchlist, "type": "custom"})

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
