from django.conf import settings
from equicast_core import (
    AccountsClient,
    GoalsClient,
    HoldingsClient,
    PiesClient,
    TransactionsClient,
    UserProfileClient,
    WatchlistsClient,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.authentication import Auth0JWTAuthentication

#: Mirrors the closed set the frontend's Settings picker offers (see
#: frontend/src/config/currencies.json) — kept here rather than fetched by
#: the frontend from an endpoint, so this is the one place both sides need
#: to stay in sync if the supported list ever changes.
SUPPORTED_CURRENCIES = {"GBP", "USD", "INR", "EUR"}

#: Valid values for a user's transaction_type — see TransactionsClient. A
#: single global setting (not per-account) so every holding across every
#: account/pie records transactions in the same shape.
TRANSACTION_TYPES = {"AVERAGE", "TRANSACTION"}

#: Valid values for a user's tax_residency (GitHub issue #94) — v1 tax logic
#: is UK-only, so "UK" is the only accepted value for now; a wider set
#: arrives once non-UK tax logic does.
TAX_RESIDENCIES = {"UK"}

#: Valid values for a user's income_tax_band (GitHub issue #94) — a
#: self-declared UK income tax band, not computed from any income data
#: equicast has. "NONE" covers a non-taxpayer (below the personal
#: allowance). Always per-user, never household-pooled — see
#: equicast_core.user_profiles.DEFAULT_INCOME_TAX_BAND.
INCOME_TAX_BANDS = {"NONE", "BASIC", "HIGHER", "ADDITIONAL"}

#: One shared client for the process, mirroring market_data/views.py's
#: module-level _client pattern.
_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)
#: Needed only to guard PATCHing transaction_type (rejected once the user
#: has any transaction recorded, across any holding) — holdings/views.py and
#: transactions/views.py hold the clients actually used for those domains'
#: CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
_transactions_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)
#: Only needed for DELETEing every domain's data on account deletion (GitHub
#: issue #158) — accounts/pies/goals/watchlists/views.py hold the clients
#: actually used for those domains' own CRUD.
_accounts_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)
_pies_client = PiesClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_pies_per_account=settings.MAX_PIES,
)
_goals_client = GoalsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_goals=settings.MAX_GOALS
)
_watchlists_client = WatchlistsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_watchlists=settings.MAX_WATCHLISTS,
)


class MeView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = _client.get_or_create_profile(request.user.user_id)
        return Response(profile)

    def patch(self, request: Request) -> Response:
        if (
            "default_currency" not in request.data
            and "transaction_type" not in request.data
            and "fx_warmup_currencies" not in request.data
            and "tax_residency" not in request.data
            and "income_tax_band" not in request.data
        ):
            return Response(
                {
                    "detail": "Missing field: default_currency, transaction_type, "
                    "fx_warmup_currencies, tax_residency, or income_tax_band."
                },
                status=400,
            )

        user_id = request.user.user_id

        if "default_currency" in request.data:
            default_currency = request.data["default_currency"]
            if default_currency not in SUPPORTED_CURRENCIES:
                return Response(
                    {"detail": f"Unknown default_currency '{default_currency}'."}, status=400
                )
            profile = _client.update_default_currency(user_id, default_currency)

        if "fx_warmup_currencies" in request.data:
            fx_warmup_currencies = request.data["fx_warmup_currencies"]
            unknown = [c for c in fx_warmup_currencies if c not in SUPPORTED_CURRENCIES]
            if unknown:
                return Response(
                    {"detail": f"Unknown fx_warmup_currencies: {', '.join(unknown)}."}, status=400
                )
            profile = _client.update_fx_warmup_currencies(user_id, fx_warmup_currencies)

        if "transaction_type" in request.data:
            transaction_type = request.data["transaction_type"]
            if transaction_type not in TRANSACTION_TYPES:
                return Response(
                    {"detail": f"Unknown transaction_type '{transaction_type}'."}, status=400
                )
            holding_ids = [h["id"] for h in _holdings_client.list_holdings(user_id)]
            if holding_ids and _transactions_client.has_transactions_for_holdings(
                user_id, holding_ids
            ):
                return Response(
                    {
                        "detail": "You have transactions recorded; transaction_type can't be "
                        "changed once transactions exist."
                    },
                    status=409,
                )
            profile = _client.update_transaction_type(user_id, transaction_type)

        if "tax_residency" in request.data:
            tax_residency = request.data["tax_residency"]
            if tax_residency not in TAX_RESIDENCIES:
                return Response({"detail": f"Unknown tax_residency '{tax_residency}'."}, status=400)
            profile = _client.update_tax_residency(user_id, tax_residency)

        if "income_tax_band" in request.data:
            income_tax_band = request.data["income_tax_band"]
            if income_tax_band not in INCOME_TAX_BANDS:
                return Response(
                    {"detail": f"Unknown income_tax_band '{income_tax_band}'."}, status=400
                )
            profile = _client.update_income_tax_band(user_id, income_tax_band)

        return Response(profile)

    def delete(self, request: Request) -> Response:
        """Permanently delete every equicast-owned record for the caller
        (GitHub issue #158) — profile, accounts, pies, goals, watchlists,
        holdings, and every holding's transactions. Their Auth0 identity
        itself is untouched (v1 scope — see the issue), so nothing stops
        them signing up again fresh afterward. Irreversible; the frontend
        gates this behind a type-to-confirm prompt before ever sending the
        request, not just a plain confirm dialog.

        Order doesn't matter for correctness (nothing read here depends on
        another client's data mid-delete, unlike a normal holding/account
        delete's cascade), but transactions/holdings go first anyway so a
        request that fails partway through never leaves transactions
        dangling for holdings that already look gone.
        """
        user_id = request.user.user_id
        holding_ids = [h["id"] for h in _holdings_client.list_holdings(user_id)]
        if holding_ids:
            _transactions_client.delete_transactions_for_holdings(user_id, holding_ids)
        _holdings_client.delete_all_holdings(user_id)
        _accounts_client.delete_all_accounts(user_id)
        _pies_client.delete_all_pies(user_id)
        _goals_client.delete_all_goals(user_id)
        _watchlists_client.delete_all_watchlists(user_id)
        _client.delete_profile(user_id)
        return Response(status=204)
