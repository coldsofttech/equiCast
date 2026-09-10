"""Class-based client for equicast's S3 JSON user-data store — goals
domain.

Same shape as `WatchlistsClient`: each user's goals live as a single JSON
object at `goals/<user_id>.json`, reads/writes use S3 conditional requests
for optimistic concurrency, and a write that loses the conditional-put race
is retried against the now-current state.

A goal isn't nested under an account or pie — it's a user-level record that
optionally *references* zero or more of them via `account_ids`/`pie_ids`, so
(like watchlists) there's no cross-account-ownership validation for the
Django view to do here — that's `backend/goals/views.py`'s job, the same
way `PiesClient` leaves `account_id` ownership to its view.

What *is* validated here is that an `account_id`/`pie_id` isn't already
referenced by a different goal — the mapping is meant to be exclusive (see
`GoalMappingConflictError`). This is the same "scan sibling records for a
clash before writing" shape as `HoldingsClient.create_holding`'s
ticker-uniqueness-within-scope check, just scoped to the whole user instead
of one parent.

Progress toward a goal's `target_amount` is computed entirely client-side
(see frontend/src/pages/goals/goalFinancials.js) from data the frontend
already has cached — this client only stores the goal's config, never a
computed value.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

#: Default ceiling on goals per user, used when `GoalsClient` isn't given
#: an explicit `max_goals`. Overridable per deployment via the `MAX_GOALS`
#: env var (see settings.py) rather than a code change, so product can
#: tune the cap without a release.
MAX_GOALS = 10

#: Fixed set of standard purposes a goal can be tagged with, plus "other"
#: for anything that doesn't fit — mirrors the frontend's closed-enum
#: purpose picker (see frontend/src/config/goalPurposes.js).
PURPOSE_CHOICES = (
    "buy_home",
    "buy_car",
    "holiday",
    "emergency_fund",
    "retirement",
    "education",
    "wedding",
    "other",
)

#: Bounds retries on a write losing the conditional-put race to a concurrent
#: writer (e.g. two browser tabs). Each retry re-reads the current state, so
#: this only loops when another write lands in the narrow window between
#: this client's own read and put.
_MAX_CONFLICT_RETRIES = 3


class GoalLimitExceededError(Exception):
    """Raised by `create_goal` when the user already has MAX_GOALS."""


class GoalNotFoundError(Exception):
    """Raised by `get_goal`/`update_goal`/`delete_goal` for an unknown goal
    id."""


class GoalMappingConflictError(Exception):
    """Raised by `create_goal`/`update_goal` when an `account_id`/`pie_id`
    being mapped onto this goal is already mapped to a different goal."""


class GoalsClient:
    """Reads and writes one user's goals as a JSON object in S3."""

    def __init__(
        self,
        bucket: str,
        s3_client: Any = None,
        region_name: str | None = None,
        max_goals: int = MAX_GOALS,
    ) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)
        self._max_goals = max_goals

    @property
    def max_goals(self) -> int:
        return self._max_goals

    def _key(self, user_id: str) -> str:
        return f"goals/{user_id}.json"

    def _load(self, user_id: str) -> tuple[list[dict[str, Any]], str | None]:
        """Return `(goals, etag)`. `etag` is `None` if the user has no
        goals object yet, so the next write knows to use
        `IfNoneMatch="*"` instead of `IfMatch` on a nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None
        body = json.loads(response["Body"].read())
        return body.get("goals", []), response["ETag"]

    def _save(self, user_id: str, goals: list[dict[str, Any]], etag: str | None) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id),
            "Body": json.dumps({"goals": goals}).encode("utf-8"),
            "ContentType": "application/json",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        self._s3.put_object(**kwargs)

    def _is_conflict(self, exc: Exception) -> bool:
        return getattr(exc, "response", {}).get("Error", {}).get("Code") == "PreconditionFailed"

    def _check_mapping_conflict(
        self,
        goals: list[dict[str, Any]],
        goal_id: str | None,
        account_ids: list[str],
        pie_ids: list[str],
    ) -> None:
        """Raise `GoalMappingConflictError` if any of `account_ids`/
        `pie_ids` is already referenced by a goal other than `goal_id`
        (`None` on create, since there's no self to exclude yet)."""
        account_id_set = set(account_ids)
        pie_id_set = set(pie_ids)
        for other in goals:
            if other["id"] == goal_id:
                continue
            clash = account_id_set & set(other["account_ids"]) or pie_id_set & set(other["pie_ids"])
            if clash:
                raise GoalMappingConflictError(
                    f"account_id/pie_id {sorted(clash)} already mapped to goal '{other['id']}'."
                )

    def list_goals(self, user_id: str) -> list[dict[str, Any]]:
        goals, _ = self._load(user_id)
        return goals

    def get_goal(self, user_id: str, goal_id: str) -> dict[str, Any]:
        """Return the goal matching `goal_id`, raising `GoalNotFoundError`
        if no such goal exists."""
        goals, _ = self._load(user_id)
        goal = next((g for g in goals if g["id"] == goal_id), None)
        if goal is None:
            raise GoalNotFoundError(f"No goal '{goal_id}' for user '{user_id}'.")
        return goal

    def create_goal(
        self,
        user_id: str,
        *,
        name: str,
        purpose: str,
        target_amount: float,
        custom_purpose: str | None = None,
        target_date: str | None = None,
        account_ids: list[str] | None = None,
        pie_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append a new goal, raising `GoalLimitExceededError` if the user
        is already at this client's `max_goals`, or
        `GoalMappingConflictError` if `account_ids`/`pie_ids` overlaps a
        different existing goal's mapping."""
        account_ids = list(account_ids or [])
        pie_ids = list(pie_ids or [])
        for _ in range(_MAX_CONFLICT_RETRIES):
            goals, etag = self._load(user_id)
            if len(goals) >= self._max_goals:
                raise GoalLimitExceededError(f"User '{user_id}' already has {self._max_goals} goals.")
            self._check_mapping_conflict(goals, None, account_ids, pie_ids)

            now = datetime.now(UTC).isoformat()
            goal = {
                "id": str(uuid.uuid4()),
                "name": name,
                "purpose": purpose,
                "custom_purpose": custom_purpose,
                "target_amount": target_amount,
                "target_date": target_date,
                "account_ids": account_ids,
                "pie_ids": pie_ids,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._save(user_id, [*goals, goal], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return goal
        raise RuntimeError(f"Too many conflicting writes to goals for user '{user_id}'.")

    def update_goal(self, user_id: str, goal_id: str, **fields: Any) -> dict[str, Any]:
        """Patch the goal matching `goal_id` with `fields`, raising
        `GoalNotFoundError` if no such goal exists, or
        `GoalMappingConflictError` if a patched `account_ids`/`pie_ids`
        overlaps a different existing goal's mapping."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            goals, etag = self._load(user_id)
            index = next((i for i, g in enumerate(goals) if g["id"] == goal_id), None)
            if index is None:
                raise GoalNotFoundError(f"No goal '{goal_id}' for user '{user_id}'.")
            updated = {**goals[index], **fields, "updated_at": datetime.now(UTC).isoformat()}
            if "account_ids" in fields or "pie_ids" in fields:
                self._check_mapping_conflict(
                    goals, goal_id, updated["account_ids"], updated["pie_ids"]
                )
            goals[index] = updated
            try:
                self._save(user_id, goals, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return updated
        raise RuntimeError(f"Too many conflicting writes to goals for user '{user_id}'.")

    def delete_goal(self, user_id: str, goal_id: str) -> None:
        """Remove the goal matching `goal_id`, raising `GoalNotFoundError`
        if no such goal exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            goals, etag = self._load(user_id)
            remaining = [g for g in goals if g["id"] != goal_id]
            if len(remaining) == len(goals):
                raise GoalNotFoundError(f"No goal '{goal_id}' for user '{user_id}'.")
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(f"Too many conflicting writes to goals for user '{user_id}'.")
