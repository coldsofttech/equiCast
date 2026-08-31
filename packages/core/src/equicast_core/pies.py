"""Class-based client for equicast's S3 JSON user-data store — pies
domain.

Same shape as `AccountsClient`: each user's pies live as a single JSON
object at `pies/<user_id>.json`, reads/writes use S3 conditional requests
for optimistic concurrency, and a write that loses the conditional-put race
is retried against the now-current state.

A pie is nested under an account (`account_id`), but ownership of that
account isn't validated here — `PiesClient` only knows about pies, the same
way `AccountsClient` only knows about accounts. The caller (the Django view)
is responsible for checking the referenced account belongs to the same user
before creating a pie against it.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

#: Default ceiling on pies per account (not per user — see Phase D req 8),
#: used when `PiesClient` isn't given an explicit `max_pies_per_account`.
#: Overridable per deployment via the `MAX_PIES` env var (see settings.py)
#: rather than a code change, so product can tune the cap without a release.
MAX_PIES = 20

#: Bounds retries on a write losing the conditional-put race to a concurrent
#: writer (e.g. two browser tabs). Each retry re-reads the current state, so
#: this only loops when another write lands in the narrow window between
#: this client's own read and put.
_MAX_CONFLICT_RETRIES = 3


class PieLimitExceededError(Exception):
    """Raised by `create_pie` when the target account already has
    max_pies_per_account pies."""


class PieNotFoundError(Exception):
    """Raised by `get_pie`/`update_pie`/`delete_pie` for an unknown pie id."""


class PiesClient:
    """Reads and writes one user's pies as a JSON object in S3."""

    def __init__(
        self,
        bucket: str,
        s3_client: Any = None,
        region_name: str | None = None,
        max_pies_per_account: int = MAX_PIES,
    ) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)
        self._max_pies_per_account = max_pies_per_account

    @property
    def max_pies_per_account(self) -> int:
        return self._max_pies_per_account

    def _key(self, user_id: str) -> str:
        return f"pies/{user_id}.json"

    def _load(self, user_id: str) -> tuple[list[dict[str, Any]], str | None]:
        """Return `(pies, etag)`. `etag` is `None` if the user has no pies
        object yet, so the next write knows to use `IfNoneMatch="*"` instead
        of `IfMatch` on a nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None
        body = json.loads(response["Body"].read())
        return body.get("pies", []), response["ETag"]

    def _save(self, user_id: str, pies: list[dict[str, Any]], etag: str | None) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id),
            "Body": json.dumps({"pies": pies}).encode("utf-8"),
            "ContentType": "application/json",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        self._s3.put_object(**kwargs)

    def _is_conflict(self, exc: Exception) -> bool:
        return getattr(exc, "response", {}).get("Error", {}).get("Code") == "PreconditionFailed"

    def list_pies(self, user_id: str, account_id: str | None = None) -> list[dict[str, Any]]:
        """Return the user's pies, optionally narrowed to one `account_id`."""
        pies, _ = self._load(user_id)
        if account_id is not None:
            pies = [p for p in pies if p["account_id"] == account_id]
        return pies

    def get_pie(self, user_id: str, pie_id: str) -> dict[str, Any]:
        """Return the pie matching `pie_id`, raising `PieNotFoundError` if no
        such pie exists."""
        pies, _ = self._load(user_id)
        pie = next((p for p in pies if p["id"] == pie_id), None)
        if pie is None:
            raise PieNotFoundError(f"No pie '{pie_id}' for user '{user_id}'.")
        return pie

    def create_pie(
        self, user_id: str, account_id: str, name: str, description: str
    ) -> dict[str, Any]:
        """Append a new pie under `account_id`, raising
        `PieLimitExceededError` if that account is already at this client's
        `max_pies_per_account`."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            pies, etag = self._load(user_id)
            existing_in_account = sum(1 for p in pies if p["account_id"] == account_id)
            if existing_in_account >= self._max_pies_per_account:
                raise PieLimitExceededError(
                    f"Account '{account_id}' already has {self._max_pies_per_account} pies."
                )
            now = datetime.now(UTC).isoformat()
            pie = {
                "id": str(uuid.uuid4()),
                "account_id": account_id,
                "name": name,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._save(user_id, [*pies, pie], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return pie
        raise RuntimeError(f"Too many conflicting writes to pies for user '{user_id}'.")

    def update_pie(self, user_id: str, pie_id: str, **fields: Any) -> dict[str, Any]:
        """Patch the pie matching `pie_id` with `fields`, raising
        `PieNotFoundError` if no such pie exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            pies, etag = self._load(user_id)
            index = next((i for i, p in enumerate(pies) if p["id"] == pie_id), None)
            if index is None:
                raise PieNotFoundError(f"No pie '{pie_id}' for user '{user_id}'.")
            updated = {
                **pies[index],
                **fields,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            pies[index] = updated
            try:
                self._save(user_id, pies, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return updated
        raise RuntimeError(f"Too many conflicting writes to pies for user '{user_id}'.")

    def delete_pie(self, user_id: str, pie_id: str) -> None:
        """Remove the pie matching `pie_id`, raising `PieNotFoundError` if no
        such pie exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            pies, etag = self._load(user_id)
            remaining = [p for p in pies if p["id"] != pie_id]
            if len(remaining) == len(pies):
                raise PieNotFoundError(f"No pie '{pie_id}' for user '{user_id}'.")
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(f"Too many conflicting writes to pies for user '{user_id}'.")

    def delete_pies_for_account(self, user_id: str, account_id: str) -> int:
        """Remove every pie under `account_id` in one write, returning how
        many were removed. Backs accounts/views.py's force-delete: unlike
        `delete_pie`, an empty match isn't an error — deleting an account
        with no pies under it is a legitimate no-op, not a bulk-delete
        target that went missing."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            pies, etag = self._load(user_id)
            remaining = [p for p in pies if p["account_id"] != account_id]
            removed = len(pies) - len(remaining)
            if removed == 0:
                return 0
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return removed
        raise RuntimeError(f"Too many conflicting writes to pies for user '{user_id}'.")
