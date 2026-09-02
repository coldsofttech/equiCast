from django.conf import settings
from equicast_core import (
    AccountAlreadyExistsError,
    AccountLimitExceededError,
    AccountNotFoundError,
    AccountsClient,
    HoldingsClient,
    PiesClient,
    TransactionsClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Fields required to create an account; description may be blank but must
#: be present so a caller doesn't silently omit it.
REQUIRED_CREATE_FIELDS = {"name", "description", "account_type", "currency", "transaction_type"}
UPDATABLE_FIELDS = {"name", "description", "account_type", "currency", "transaction_type"}

#: Valid values for an account's transaction_type — see TransactionsClient.
TRANSACTION_TYPES = {"AVERAGE", "TRANSACTION"}

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
#: Needed to guard PATCHing transaction_type (rejected once the account has
#: any transactions recorded under it — see AccountDetailView.patch) and to
#: cascade-delete transactions under AccountDetailView.delete's force path
#: — transactions/views.py holds the client actually used for transactions
#: CRUD.
_transactions_client = TransactionsClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_transactions_for_holding=settings.MAX_TRANSACTIONS_FOR_HOLDING,
)


def _holding_ids_for_account(user_id: str, account_id: str, pies: list) -> list[str]:
    """Every holding_id under `account_id` — directly, or via one of
    `pies` (already fetched by the caller) — used to check for/cascade-
    delete this account's transactions, which are keyed by holding_id
    rather than account_id."""
    pie_ids = {p["id"] for p in pies}
    holdings = _holdings_client.list_holdings(user_id)
    return [h["id"] for h in holdings if h["account_id"] == account_id or h["pie_id"] in pie_ids]


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
        holdings = _holdings_client.list_holdings(user_id)
        return Response(_nest_pies_and_holdings(accounts, pies, holdings))

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        transaction_type = request.data["transaction_type"]
        if transaction_type not in TRANSACTION_TYPES:
            return Response(
                {"detail": f"Unknown transaction_type '{transaction_type}'."}, status=400
            )

        try:
            account = _client.create_account(
                request.user.user_id,
                name=request.data["name"],
                description=request.data["description"],
                account_type=request.data["account_type"],
                currency=request.data["currency"],
                transaction_type=transaction_type,
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
        holdings = _holdings_client.list_holdings(user_id)
        nested = _nest_pies_and_holdings([account], pies, holdings)[0]
        return Response(nested)

    def patch(self, request: Request, account_id: str) -> Response:
        user_id = request.user.user_id
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}

        if "transaction_type" in fields:
            if fields["transaction_type"] not in TRANSACTION_TYPES:
                return Response(
                    {"detail": f"Unknown transaction_type '{fields['transaction_type']}'."},
                    status=400,
                )
            pies = _pies_client.list_pies(user_id, account_id=account_id)
            holding_ids = _holding_ids_for_account(user_id, account_id, pies)
            if holding_ids and _transactions_client.has_transactions_for_holdings(
                user_id, holding_ids
            ):
                return Response(
                    {
                        "detail": "Account has transactions recorded; transaction_type can't "
                        "be changed once transactions exist."
                    },
                    status=409,
                )

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
