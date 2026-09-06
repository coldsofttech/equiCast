from datetime import UTC, datetime
from typing import Any

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
    TransactionsClient,
    UserProfileClient,
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
#: Needed only to cascade-delete a pie's holdings' transactions under
#: PieDetailView.delete's force path — transactions/views.py holds the
#: client actually used for transactions CRUD.
_transactions_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)
#: Needed only to read the user's default_currency, so a pie holding's
#: current_price can be converted the same way transactions/views.py
#: converts average_price/invested/dividends (see resolve_converted_amounts
#: there) — identity/views.py holds the client actually used for profile CRUD.
_profile_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)


def _enrich_holdings(user_id: str, holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return `holdings` with market-derived display/valuation fields merged
    in: `name`/`sector`/`industry`/`website` (from
    `MarketDataClient.get_profile` — `website` backs the frontend's
    favicon-based AssetIcon) and `current_price_native`/`current_price`
    (today's price, FX-converted to the user's `default_currency` — the
    same convention `average_price`/`invested`/`dividends` already use, see
    `transactions.views.resolve_converted_amounts`), so the frontend can
    derive current value/profit-loss without a market-data round trip per
    ticker.

    Batches lookups so a pie (or a whole account's worth of pies) with many
    holdings costs one profile fetch per distinct ticker and one FX lookup
    per distinct native currency, not one per holding. A field is `None`
    whenever it can't be resolved (unpublished ticker, no FX rate) rather
    than raising — same degrade-gracefully behavior as
    `resolve_converted_amounts`.
    """
    if not holdings:
        return holdings

    default_currency = _profile_client.get_or_create_profile(user_id)["default_currency"]
    today = datetime.now(UTC).date().isoformat()

    profiles: dict[tuple[str, str], dict[str, Any] | None] = {}
    for holding in holdings:
        key = (holding["asset_class"], holding["ticker"])
        if key not in profiles:
            profiles[key] = _market_data_client.get_profile(*key)

    fx_rates: dict[str, float | None] = {}
    for profile in profiles.values():
        native_currency = profile.get("currency") if profile else None
        if native_currency and native_currency not in fx_rates:
            fx_rates[native_currency] = _market_data_client.get_fx_rate_on_date(
                native_currency, default_currency, today
            )

    enriched = []
    for holding in holdings:
        profile = profiles[(holding["asset_class"], holding["ticker"])]
        native_currency = profile.get("currency") if profile else None
        current_price_native = profile.get("day_close") if profile else None
        rate = fx_rates.get(native_currency) if native_currency else None
        current_price = (
            current_price_native * rate
            if current_price_native is not None and rate is not None
            else None
        )
        enriched.append(
            {
                **holding,
                "name": profile.get("name") if profile else None,
                "sector": profile.get("sector") if profile else None,
                "industry": profile.get("industry") if profile else None,
                "website": profile.get("website") if profile else None,
                "current_price_native": current_price_native,
                "current_price": current_price,
            }
        )
    return enriched


class PieListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        account_id = request.query_params.get("account_id")
        pies = _client.list_pies(request.user.user_id, account_id=account_id)

        pie_ids = {pie["id"] for pie in pies}
        holdings = [
            h
            for h in _holdings_client.list_holdings(request.user.user_id)
            if h["pie_id"] in pie_ids
        ]
        holdings_by_pie: dict[str, list[dict[str, Any]]] = {}
        for holding in _enrich_holdings(request.user.user_id, holdings):
            holdings_by_pie.setdefault(holding["pie_id"], []).append(holding)

        return Response(
            [{**pie, "holdings": holdings_by_pie.get(pie["id"], [])} for pie in pies]
        )

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
        return Response({**pie, "holdings": _enrich_holdings(request.user.user_id, holdings)})

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
                _transactions_client.delete_transactions_for_holdings(
                    request.user.user_id, [h["id"] for h in holdings]
                )
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
        except HoldingAlreadyExistsError:
            # Static, caller-agnostic message rather than str(exc) — same
            # py/stack-trace-exposure reasoning as AccountListView.post's
            # 409 (see accounts/views.py).
            return Response({"detail": "Ticker is already held in this pie."}, status=409)
        except HoldingLimitExceededError:
            cap = _holdings_client.max_holdings_for_pie
            return Response({"detail": f"Pie holding limit reached (max {cap})."}, status=409)
        except AllocationError:
            return Response({"detail": "Pie holdings must sum to exactly 100%."}, status=400)

        # Not enriched (see _enrich_holdings) — remove/reallocate-only calls
        # must not touch market data (see
        # test_put_removes_and_reallocates_without_touching_market_data), and
        # the caller re-fetches the pie (GET /pies/<id>, which does enrich)
        # right after a successful sync anyway (see PieDetailPage's
        # handleSaveAllocation).
        return Response({**pie, "holdings": holdings})
