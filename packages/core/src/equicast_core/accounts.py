"""Class-based client for equicast's S3 JSON user-data store — accounts
domain.

Generic across consumers the same way `MarketDataClient`/`UserProfileClient`
are. Each user's accounts live as a single JSON object at
`accounts/<user_id>.json`; reads/writes use S3 conditional requests
(`IfNoneMatch`/`IfMatch` on the object's ETag) for the same optimistic-
concurrency guarantee `UserProfileClient` gets from DynamoDB's
`ConditionExpression`, since S3 has no equivalent conditional-update
primitive for JSON blobs — only whole-object conditional puts.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

#: Product-defined ceiling on accounts per user (see Phase D req 7).
MAX_ACCOUNTS = 5

#: Bounds retries on a write losing the conditional-put race to a concurrent
#: writer (e.g. two browser tabs). Each retry re-reads the current state, so
#: this only loops when another write lands in the narrow window between
#: this client's own read and put.
_MAX_CONFLICT_RETRIES = 3


class AccountLimitExceededError(Exception):
    """Raised by `create_account` when the user already has MAX_ACCOUNTS."""


class AccountNotFoundError(Exception):
    """Raised by `update_account`/`delete_account` for an unknown account id."""


class AccountsClient:
    """Reads and writes one user's accounts as a JSON object in S3."""

    def __init__(self, bucket: str, s3_client: Any = None, region_name: str | None = None) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)

    def _key(self, user_id: str) -> str:
        return f"accounts/{user_id}.json"

    def _load(self, user_id: str) -> tuple[list[dict[str, Any]], str | None]:
        """Return `(accounts, etag)`. `etag` is `None` if the user has no
        accounts object yet, so the next write knows to use `IfNoneMatch="*"`
        instead of `IfMatch` on a nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None
        body = json.loads(response["Body"].read())
        return body.get("accounts", []), response["ETag"]

    def _save(self, user_id: str, accounts: list[dict[str, Any]], etag: str | None) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id),
            "Body": json.dumps({"accounts": accounts}).encode("utf-8"),
            "ContentType": "application/json",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        self._s3.put_object(**kwargs)

    def _is_conflict(self, exc: Exception) -> bool:
        return getattr(exc, "response", {}).get("Error", {}).get("Code") == "PreconditionFailed"

    def list_accounts(self, user_id: str) -> list[dict[str, Any]]:
        accounts, _ = self._load(user_id)
        return accounts

    def create_account(
        self, user_id: str, name: str, description: str, account_type: str, currency: str
    ) -> dict[str, Any]:
        """Append a new account, raising `AccountLimitExceededError` if the
        user is already at `MAX_ACCOUNTS`."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            accounts, etag = self._load(user_id)
            if len(accounts) >= MAX_ACCOUNTS:
                raise AccountLimitExceededError(
                    f"User '{user_id}' already has {MAX_ACCOUNTS} accounts."
                )
            now = datetime.now(UTC).isoformat()
            account = {
                "id": str(uuid.uuid4()),
                "name": name,
                "description": description,
                "account_type": account_type,
                "currency": currency,
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._save(user_id, [*accounts, account], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return account
        raise RuntimeError(f"Too many conflicting writes to accounts for user '{user_id}'.")

    def update_account(self, user_id: str, account_id: str, **fields: Any) -> dict[str, Any]:
        """Patch the account matching `account_id` with `fields`, raising
        `AccountNotFoundError` if no such account exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            accounts, etag = self._load(user_id)
            index = next((i for i, a in enumerate(accounts) if a["id"] == account_id), None)
            if index is None:
                raise AccountNotFoundError(f"No account '{account_id}' for user '{user_id}'.")
            updated = {
                **accounts[index],
                **fields,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            accounts[index] = updated
            try:
                self._save(user_id, accounts, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return updated
        raise RuntimeError(f"Too many conflicting writes to accounts for user '{user_id}'.")

    def delete_account(self, user_id: str, account_id: str) -> None:
        """Remove the account matching `account_id`, raising
        `AccountNotFoundError` if no such account exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            accounts, etag = self._load(user_id)
            remaining = [a for a in accounts if a["id"] != account_id]
            if len(remaining) == len(accounts):
                raise AccountNotFoundError(f"No account '{account_id}' for user '{user_id}'.")
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(f"Too many conflicting writes to accounts for user '{user_id}'.")
