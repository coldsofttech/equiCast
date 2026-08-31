from django.conf import settings
from equicast_core import (
    AccountLimitExceededError,
    AccountNotFoundError,
    AccountsClient,
    PiesClient,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Fields required to create an account; description may be blank but must
#: be present so a caller doesn't silently omit it.
REQUIRED_CREATE_FIELDS = {"name", "description", "account_type", "currency"}
UPDATABLE_FIELDS = {"name", "description", "account_type", "currency"}

#: One shared client for the process, mirroring market_data/views.py's
#: module-level _client pattern.
_client = AccountsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_accounts=settings.MAX_ACCOUNTS
)
#: Needed to nest a pie's account under `AccountDetailView.get` and to
#: guard/force-delete pies under `AccountDetailView.delete` — pies/views.py
#: holds the client actually used for pies CRUD.
_pies_client = PiesClient(
    settings.USER_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    max_pies_per_account=settings.MAX_PIES,
)


class AccountListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(_client.list_accounts(request.user.user_id))

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        try:
            account = _client.create_account(
                request.user.user_id,
                name=request.data["name"],
                description=request.data["description"],
                account_type=request.data["account_type"],
                currency=request.data["currency"],
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
        try:
            account = _client.get_account(request.user.user_id, account_id)
        except AccountNotFoundError:
            return Response(status=404)
        pies = _pies_client.list_pies(request.user.user_id, account_id=account_id)
        return Response({**account, "pies": pies})

    def patch(self, request: Request, account_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            account = _client.update_account(request.user.user_id, account_id, **fields)
        except AccountNotFoundError:
            return Response(status=404)
        return Response(account)

    def delete(self, request: Request, account_id: str) -> Response:
        force = request.query_params.get("force", "").lower() == "true"
        pies = _pies_client.list_pies(request.user.user_id, account_id=account_id)
        if pies and not force:
            return Response(
                {
                    "detail": "Account has pies; delete them first, "
                    "or retry with ?force=true to delete them along with the account."
                },
                status=409,
            )

        try:
            if force and pies:
                _pies_client.delete_pies_for_account(request.user.user_id, account_id)
            _client.delete_account(request.user.user_id, account_id)
        except AccountNotFoundError:
            return Response(status=404)
        return Response(status=204)
