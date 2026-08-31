from django.conf import settings
from equicast_core import (
    AccountsClient,
    PieLimitExceededError,
    PieNotFoundError,
    PiesClient,
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


class PieListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        account_id = request.query_params.get("account_id")
        return Response(_client.list_pies(request.user.user_id, account_id=account_id))

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
        return Response(pie)

    def patch(self, request: Request, pie_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}
        try:
            pie = _client.update_pie(request.user.user_id, pie_id, **fields)
        except PieNotFoundError:
            return Response(status=404)
        return Response(pie)

    def delete(self, request: Request, pie_id: str) -> Response:
        try:
            _client.delete_pie(request.user.user_id, pie_id)
        except PieNotFoundError:
            return Response(status=404)
        return Response(status=204)
