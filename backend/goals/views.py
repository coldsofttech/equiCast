from typing import Any

from django.conf import settings
from equicast_core import (
    AccountsClient,
    GoalLimitExceededError,
    GoalMappingConflictError,
    GoalNotFoundError,
    GoalsClient,
    PiesClient,
    PURPOSE_CHOICES,
)
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Fields required to create a goal — purpose/target_amount are the only
#: ones a caller can't sensibly omit; custom_purpose/target_date/
#: account_ids/pie_ids all have sensible empty defaults (see
#: OPTIONAL_CREATE_FIELDS).
REQUIRED_CREATE_FIELDS = {"name", "purpose", "target_amount"}
OPTIONAL_CREATE_FIELDS = {"custom_purpose", "target_date", "account_ids", "pie_ids"}
UPDATABLE_FIELDS = {
    "name",
    "purpose",
    "custom_purpose",
    "target_amount",
    "target_date",
    "account_ids",
    "pie_ids",
    "status",
}
STATUS_CHOICES = {"active", "achieved"}

#: One shared client for the process, mirroring watchlists/views.py's
#: module-level _client pattern.
_client = GoalsClient(
    settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION, max_goals=settings.MAX_GOALS
)
#: Needed only to validate that a submitted account_id/pie_id belongs to
#: the caller before it's ever handed to _client — same reasoning as
#: pies/views.py's _accounts_client (account ownership isn't validated
#: inside GoalsClient/PiesClient themselves).
_accounts_client = AccountsClient(settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION)
_pies_client = PiesClient(settings.USER_DATA_BUCKET, region_name=settings.AWS_REGION)


def _validate_purpose(data: dict[str, Any]) -> str | None:
    """Return a 400 detail message if `data`'s purpose/custom_purpose
    fields aren't valid, else `None`."""
    purpose = data.get("purpose")
    if purpose is not None and purpose not in PURPOSE_CHOICES:
        return f"Unknown purpose. Must be one of: {', '.join(PURPOSE_CHOICES)}."
    if purpose == "other" and not data.get("custom_purpose"):
        return "custom_purpose is required when purpose is 'other'."
    return None


def _validate_status(data: dict[str, Any]) -> str | None:
    status = data.get("status")
    if status is not None and status not in STATUS_CHOICES:
        return f"Unknown status. Must be one of: {', '.join(sorted(STATUS_CHOICES))}."
    return None


def _validate_mapping(user_id: str, data: dict[str, Any]) -> str | None:
    """Return a 400 detail message if `data`'s account_ids/pie_ids
    reference unknown resources, or a pie's own parent account is also
    included on the same goal (which would double-count that pie's
    holdings — see equicast_core.goals.GoalsClient's docstring). `None`
    if account_ids/pie_ids are absent from `data` entirely or both valid."""
    if "account_ids" not in data and "pie_ids" not in data:
        return None
    account_ids = set(data.get("account_ids") or [])
    pie_ids = set(data.get("pie_ids") or [])

    caller_accounts = _accounts_client.list_accounts(user_id)
    unknown_accounts = account_ids - {a["id"] for a in caller_accounts}
    if unknown_accounts:
        return f"Unknown account_id(s): {', '.join(sorted(unknown_accounts))}."

    caller_pies = _pies_client.list_pies(user_id)
    pies_by_id = {p["id"]: p for p in caller_pies}
    unknown_pies = pie_ids - pies_by_id.keys()
    if unknown_pies:
        return f"Unknown pie_id(s): {', '.join(sorted(unknown_pies))}."

    self_overlap = {
        pie_id for pie_id in pie_ids if pies_by_id[pie_id]["account_id"] in account_ids
    }
    if self_overlap:
        return (
            f"pie_id(s) {', '.join(sorted(self_overlap))} already covered by an "
            "account_id also mapped to this goal."
        )
    return None


class GoalListView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(_client.list_goals(request.user.user_id))

    def post(self, request: Request) -> Response:
        missing = REQUIRED_CREATE_FIELDS - request.data.keys()
        if missing:
            return Response(
                {"detail": f"Missing field(s): {', '.join(sorted(missing))}."}, status=400
            )

        purpose_error = _validate_purpose(request.data)
        if purpose_error:
            return Response({"detail": purpose_error}, status=400)

        mapping_error = _validate_mapping(request.user.user_id, request.data)
        if mapping_error:
            return Response({"detail": mapping_error}, status=400)

        optional_fields = {k: v for k, v in request.data.items() if k in OPTIONAL_CREATE_FIELDS}
        try:
            goal = _client.create_goal(
                request.user.user_id,
                name=request.data["name"],
                purpose=request.data["purpose"],
                target_amount=request.data["target_amount"],
                **optional_fields,
            )
        except GoalLimitExceededError:
            # Static, caller-agnostic message — same py/stack-trace-exposure
            # reasoning as AccountListView.post's 409 (see accounts/views.py).
            detail = f"Goal limit reached (max {_client.max_goals})."
            return Response({"detail": detail}, status=409)
        except GoalMappingConflictError:
            detail = "One or more account_id/pie_id is already mapped to another goal."
            return Response({"detail": detail}, status=409)
        return Response(goal, status=201)


class GoalDetailView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, goal_id: str) -> Response:
        try:
            goal = _client.get_goal(request.user.user_id, goal_id)
        except GoalNotFoundError:
            return Response(status=404)
        return Response(goal)

    def patch(self, request: Request, goal_id: str) -> Response:
        fields = {k: v for k, v in request.data.items() if k in UPDATABLE_FIELDS}

        purpose_error = _validate_purpose(fields)
        if purpose_error:
            return Response({"detail": purpose_error}, status=400)
        status_error = _validate_status(fields)
        if status_error:
            return Response({"detail": status_error}, status=400)
        mapping_error = _validate_mapping(request.user.user_id, fields)
        if mapping_error:
            return Response({"detail": mapping_error}, status=400)

        try:
            goal = _client.update_goal(request.user.user_id, goal_id, **fields)
        except GoalNotFoundError:
            return Response(status=404)
        except GoalMappingConflictError:
            detail = "One or more account_id/pie_id is already mapped to another goal."
            return Response({"detail": detail}, status=409)
        return Response(goal)

    def delete(self, request: Request, goal_id: str) -> Response:
        try:
            _client.delete_goal(request.user.user_id, goal_id)
        except GoalNotFoundError:
            return Response(status=404)
        return Response(status=204)
