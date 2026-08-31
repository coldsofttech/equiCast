"""Class-based client for equicast's S3 JSON user-data store — watchlists
domain.

Same shape as `AccountsClient`: each user's watchlists live as a single JSON
object at `watchlists/<user_id>.json`, reads/writes use S3 conditional
requests for optimistic concurrency, and a write that loses the
conditional-put race is retried against the now-current state.

Unlike a pie, a watchlist isn't nested under an account — it's a user-level
list (a user doesn't need an account to watchlist a few holdings), so there's
no `account_id` field and no cross-account-ownership validation for the
Django view to do.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

#: Default ceiling on watchlists per user, used when `WatchlistsClient` isn't
#: given an explicit `max_watchlists`. Overridable per deployment via the
#: `MAX_WATCHLISTS` env var (see settings.py) rather than a code change, so
#: product can tune the cap without a release.
MAX_WATCHLISTS = 5

#: Bounds retries on a write losing the conditional-put race to a concurrent
#: writer (e.g. two browser tabs). Each retry re-reads the current state, so
#: this only loops when another write lands in the narrow window between
#: this client's own read and put.
_MAX_CONFLICT_RETRIES = 3


class WatchlistLimitExceededError(Exception):
    """Raised by `create_watchlist` when the user already has
    MAX_WATCHLISTS."""


class WatchlistNotFoundError(Exception):
    """Raised by `get_watchlist`/`update_watchlist`/`delete_watchlist` for an
    unknown watchlist id."""


class WatchlistsClient:
    """Reads and writes one user's watchlists as a JSON object in S3."""

    def __init__(
        self,
        bucket: str,
        s3_client: Any = None,
        region_name: str | None = None,
        max_watchlists: int = MAX_WATCHLISTS,
    ) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)
        self._max_watchlists = max_watchlists

    @property
    def max_watchlists(self) -> int:
        return self._max_watchlists

    def _key(self, user_id: str) -> str:
        return f"watchlists/{user_id}.json"

    def _load(self, user_id: str) -> tuple[list[dict[str, Any]], str | None]:
        """Return `(watchlists, etag)`. `etag` is `None` if the user has no
        watchlists object yet, so the next write knows to use
        `IfNoneMatch="*"` instead of `IfMatch` on a nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None
        body = json.loads(response["Body"].read())
        return body.get("watchlists", []), response["ETag"]

    def _save(self, user_id: str, watchlists: list[dict[str, Any]], etag: str | None) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id),
            "Body": json.dumps({"watchlists": watchlists}).encode("utf-8"),
            "ContentType": "application/json",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        self._s3.put_object(**kwargs)

    def _is_conflict(self, exc: Exception) -> bool:
        return getattr(exc, "response", {}).get("Error", {}).get("Code") == "PreconditionFailed"

    def list_watchlists(self, user_id: str) -> list[dict[str, Any]]:
        watchlists, _ = self._load(user_id)
        return watchlists

    def get_watchlist(self, user_id: str, watchlist_id: str) -> dict[str, Any]:
        """Return the watchlist matching `watchlist_id`, raising
        `WatchlistNotFoundError` if no such watchlist exists."""
        watchlists, _ = self._load(user_id)
        watchlist = next((w for w in watchlists if w["id"] == watchlist_id), None)
        if watchlist is None:
            raise WatchlistNotFoundError(f"No watchlist '{watchlist_id}' for user '{user_id}'.")
        return watchlist

    def create_watchlist(self, user_id: str, name: str, description: str) -> dict[str, Any]:
        """Append a new watchlist, raising `WatchlistLimitExceededError` if
        the user is already at this client's `max_watchlists`."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            watchlists, etag = self._load(user_id)
            if len(watchlists) >= self._max_watchlists:
                raise WatchlistLimitExceededError(
                    f"User '{user_id}' already has {self._max_watchlists} watchlists."
                )
            now = datetime.now(UTC).isoformat()
            watchlist = {
                "id": str(uuid.uuid4()),
                "name": name,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._save(user_id, [*watchlists, watchlist], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return watchlist
        raise RuntimeError(f"Too many conflicting writes to watchlists for user '{user_id}'.")

    def update_watchlist(self, user_id: str, watchlist_id: str, **fields: Any) -> dict[str, Any]:
        """Patch the watchlist matching `watchlist_id` with `fields`, raising
        `WatchlistNotFoundError` if no such watchlist exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            watchlists, etag = self._load(user_id)
            index = next((i for i, w in enumerate(watchlists) if w["id"] == watchlist_id), None)
            if index is None:
                raise WatchlistNotFoundError(f"No watchlist '{watchlist_id}' for user '{user_id}'.")
            updated = {
                **watchlists[index],
                **fields,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            watchlists[index] = updated
            try:
                self._save(user_id, watchlists, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return updated
        raise RuntimeError(f"Too many conflicting writes to watchlists for user '{user_id}'.")

    def delete_watchlist(self, user_id: str, watchlist_id: str) -> None:
        """Remove the watchlist matching `watchlist_id`, raising
        `WatchlistNotFoundError` if no such watchlist exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            watchlists, etag = self._load(user_id)
            remaining = [w for w in watchlists if w["id"] != watchlist_id]
            if len(remaining) == len(watchlists):
                raise WatchlistNotFoundError(f"No watchlist '{watchlist_id}' for user '{user_id}'.")
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(f"Too many conflicting writes to watchlists for user '{user_id}'.")
