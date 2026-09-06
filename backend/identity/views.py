from django.conf import settings
from equicast_core import HoldingsClient, TransactionsClient, UserProfileClient
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


class MeView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = _client.get_or_create_profile(request.user.user_id)
        return Response(profile)

    def patch(self, request: Request) -> Response:
        if "default_currency" not in request.data and "transaction_type" not in request.data:
            return Response(
                {"detail": "Missing field: default_currency or transaction_type."}, status=400
            )

        user_id = request.user.user_id

        if "default_currency" in request.data:
            default_currency = request.data["default_currency"]
            if default_currency not in SUPPORTED_CURRENCIES:
                return Response(
                    {"detail": f"Unknown default_currency '{default_currency}'."}, status=400
                )
            profile = _client.update_default_currency(user_id, default_currency)

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

        return Response(profile)
