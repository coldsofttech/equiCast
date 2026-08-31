from django.conf import settings
from equicast_core import AccountLimitExceededError, AccountNotFoundError, AccountsClient
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
_client = AccountsClient(settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION)


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
        except AccountLimitExceededError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(account, status=201)


class AccountDetailView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, account_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            account = _client.update_account(request.user.user_id, account_id, **fields)
        except AccountNotFoundError:
            return Response(status=404)
        return Response(account)

    def delete(self, request: Request, account_id: str) -> Response:
        try:
            _client.delete_account(request.user.user_id, account_id)
        except AccountNotFoundError:
            return Response(status=404)
        return Response(status=204)
