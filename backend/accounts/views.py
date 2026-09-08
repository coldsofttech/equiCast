from typing import Any

from django.conf import settings
from equicast_core import (
    AccountAlreadyExistsError,
    AccountLimitExceededError,
    AccountNotFoundError,
    AccountsClient,
    HoldingsClient,
    MarketDataClient,
    PiesClient,
    TransactionsClient,
    UserProfileClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Fields required to create an account; description may be blank but must
#: be present so a caller doesn't silently omit it.
REQUIRED_CREATE_FIELDS = {"name", "description", "account_type", "currency"}
#: Optional at create time — an account without one falls back to a default
#: icon client-side, same reasoning as pies/views.py's OPTIONAL_CREATE_FIELDS.
OPTIONAL_CREATE_FIELDS = {"icon"}
UPDATABLE_FIELDS = {"name", "description", "account_type", "currency", "icon"}

#: One shared client for the process, mirroring market_data/views.py's
#: module-level _client pattern.
_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)
#: Needed to nest an account's pies under `AccountListView.get`/
#: `AccountDetailView.get` and to guard/force-delete pies under
#: `AccountDetailView.delete` — pies/views.py holds the client actually
#: used for pies CRUD.
_pies_client = PiesClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_pies_per_account=settings.MAX_PIES,
)
#: Needed to nest holdings (both under each pie and directly under the
#: account) and to guard/force-delete direct account holdings under
#: `AccountDetailView.delete` — holdings/views.py holds the client actually
#: used for account-direct/watchlist holdings CRUD.
_holdings_client = HoldingsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_holdings_for_account=settings.MAX_HOLDINGS_FOR_ACCOUNT,
    max_holdings_for_pie=settings.MAX_HOLDINGS_FOR_PIE,
    max_holdings_for_watchlist=settings.MAX_HOLDINGS_FOR_WATCHLIST,
)
#: Needed only to cascade-delete transactions under AccountDetailView.delete's
#: force path — transactions/views.py holds the client actually used for
#: transactions CRUD.
_transactions_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)
#: Needed to merge each holding's current_price_native/current_price (and
#: name/sector/industry/website/market_cap) in via `enrich_holdings` —
#: pies/views.py holds the client instance actually used to validate a
#: ticker has market data before it's added to a pie.
_market_data_client = MarketDataClient(settings.MARKET_DATA_BUCKET, region_name=settings.AWS_REGION)
#: Needed only to read the user's default_currency, so `enrich_holdings`
#: converts current_price the same way transactions/views.py converts
#: average_price/invested/dividends (see resolve_converted_amounts there) —
#: identity/views.py holds the client actually used for profile CRUD.
_profile_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)


def _enrich_holdings(user_id: str, holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve `user_id`'s `default_currency` and delegate to
    `MarketDataClient.enrich_holdings` for the actual catalog-backed
    name/sector/industry/website/market_cap/current_price_native/
    current_price merge — see that method's docstring for what it fills in
    and why. Holdings here
    may be a mix of account-direct and pie-nested (both carry the same
    `asset_class`/`ticker` shape `enrich_holdings` needs), so this is called
    once on the full flat list before `_nest_pies_and_holdings` splits it
    back apart, rather than once per pie. Short-circuits on an empty
    `holdings` before even reading the caller's profile, since there'd be
    nothing to enrich either way."""
    if not holdings:
        return holdings
    default_currency = _profile_client.get_or_create_profile(user_id)["default_currency"]
    return _market_data_client.enrich_holdings(holdings, default_currency)


def _nest_pies_and_holdings(accounts, pies, holdings):
    """Group `pies` by `account_id` and `holdings` by `pie_id`/`account_id`
    (direct), returning each account with its pies (each carrying its own
    `holdings`) and its own direct `holdings` nested in. `pies`/`holdings`
    are expected to already be the full per-user lists — grouping happens
    in memory here rather than issuing one S3 read per account, since
    PiesClient/HoldingsClient each return their whole per-user JSON object
    in a single read regardless of filter."""
    pies_by_account: dict[str, list] = {}
    for pie in pies:
        pies_by_account.setdefault(pie["account_id"], []).append(pie)

    holdings_by_pie: dict[str, list] = {}
    holdings_by_account: dict[str, list] = {}
    for holding in holdings:
        if holding["pie_id"] is not None:
            holdings_by_pie.setdefault(holding["pie_id"], []).append(holding)
        elif holding["account_id"] is not None:
            holdings_by_account.setdefault(holding["account_id"], []).append(holding)

    return [
        {
            **account,
            "pies": [
                {**pie, "holdings": holdings_by_pie.get(pie["id"], [])}
                for pie in pies_by_account.get(account["id"], [])
            ],
            "holdings": holdings_by_account.get(account["id"], []),
        }
        for account in accounts
    ]


class AccountListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user_id = request.user.user_id
        accounts = _client.list_accounts(user_id)
        pies = _pies_client.list_pies(user_id)
        holdings = _enrich_holdings(user_id, _holdings_client.list_holdings(user_id))
        return Response(_nest_pies_and_holdings(accounts, pies, holdings))

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        optional_fields = {k: v for k, v in request.data.items() if k in OPTIONAL_CREATE_FIELDS}
        try:
            account = _client.create_account(
                request.user.user_id,
                name=request.data["name"],
                description=request.data["description"],
                account_type=request.data["account_type"],
                currency=request.data["currency"],
                **optional_fields,
            )
        except AccountAlreadyExistsError:
            return Response(
                {"detail": f"An account named '{request.data['name']}' already exists."},
                status=409,
            )
        except AccountLimitExceededError:
            # A static, caller-agnostic message rather than str(exc) — the
            # exception text embeds the caller's own user_id, and echoing
            # exception content back into a response is exactly the pattern
            # CodeQL's py/stack-trace-exposure flags, regardless of whether
            # this particular message is sensitive.
            return Response(
                {"detail": f"Account limit reached (max {_client.max_accounts})."}, status=409
            )
        return Response(account, status=201)


class AccountDetailView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, account_id: str) -> Response:
        user_id = request.user.user_id
        try:
            account = _client.get_account(user_id, account_id)
        except AccountNotFoundError:
            return Response(status=404)
        pies = _pies_client.list_pies(user_id, account_id=account_id)
        holdings = _enrich_holdings(user_id, _holdings_client.list_holdings(user_id))
        nested = _nest_pies_and_holdings([account], pies, holdings)[0]
        return Response(nested)

    def patch(self, request: Request, account_id: str) -> Response:
        user_id = request.user.user_id
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}

        try:
            account = _client.update_account(user_id, account_id, **fields)
        except AccountAlreadyExistsError:
            return Response(
                {"detail": f"An account named '{fields['name']}' already exists."}, status=409
            )
        except AccountNotFoundError:
            return Response(status=404)
        return Response(account)

    def delete(self, request: Request, account_id: str) -> Response:
        user_id = request.user.user_id
        force = request.query_params.get("force", "").lower() == "true"
        # Pie-nested holdings aren't checked separately here — a pie with
        # holdings is already covered by the `pies` check below (an account
        # can't be deleted while it still has pies at all, regardless of
        # whether those pies hold anything), and force-deleting the pies
        # cascades into their holdings too.
        pies = _pies_client.list_pies(user_id, account_id=account_id)
        direct_holdings = _holdings_client.list_holdings(user_id, account_id=account_id)
        if (pies or direct_holdings) and not force:
            return Response(
                {
                    "detail": "Account has pies and/or holdings; delete them first, "
                    "or retry with ?force=true to delete them along with the account."
                },
                status=409,
            )

        try:
            if force and pies:
                pie_ids = [pie["id"] for pie in pies]
                pie_holding_ids = [
                    h["id"]
                    for h in _holdings_client.list_holdings(user_id)
                    if h["pie_id"] in set(pie_ids)
                ]
                if pie_holding_ids:
                    _transactions_client.delete_transactions_for_holdings(user_id, pie_holding_ids)
                _holdings_client.delete_holdings_for_pies(user_id, pie_ids)
                _pies_client.delete_pies_for_account(user_id, account_id)
            if force and direct_holdings:
                _transactions_client.delete_transactions_for_holdings(
                    user_id, [h["id"] for h in direct_holdings]
                )
                _holdings_client.delete_holdings_for_account(user_id, account_id)
            _client.delete_account(user_id, account_id)
        except AccountNotFoundError:
            return Response(status=404)
        return Response(status=204)
