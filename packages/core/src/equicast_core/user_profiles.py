"""Class-based client for equicast's DynamoDB user-profile store.

Generic across consumers the same way `MarketDataClient` is — it only knows
the table's shape (a `user_id`-keyed item, no sort key, no GSI: every access
pattern so far is a point lookup by the caller's own ID), nothing about
Django or any particular caller.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any

import boto3

#: Applied to a brand-new profile on first login. GBP, not USD — equiCast's
#: default currency from the app's perspective.
DEFAULT_CURRENCY = "GBP"


class UserProfileClient:
    """Reads and upserts items in one DynamoDB user-profiles table."""

    def __init__(self, table_name: str, resource: Any = None) -> None:
        self._table_name = table_name
        self._resource = resource or boto3.resource("dynamodb")

    @cached_property
    def _table(self) -> Any:
        # Resolved lazily (not in __init__) so constructing a client with an
        # unset table_name — e.g. USER_PROFILES_TABLE unconfigured locally —
        # doesn't blow up at import time; boto3.resource("dynamodb").Table()
        # validates its name argument eagerly, unlike MarketDataClient's
        # boto3.client("s3") (bucket is a per-call argument there, not
        # baked into construction).
        return self._resource.Table(self._table_name)

    def get_or_create_profile(self, user_id: str) -> dict[str, Any]:
        """Return the profile item for `user_id`, creating it with
        `default_currency=DEFAULT_CURRENCY` if this is their first login.

        The create is a conditional put (`attribute_not_exists(user_id)`) so
        a concurrent first login can't clobber a profile the user has
        already started customizing — on that race, this re-fetches and
        returns the winning write instead of overwriting it."""
        response = self._table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is not None:
            return item

        item = {"user_id": user_id, "default_currency": DEFAULT_CURRENCY}
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(user_id)",
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return self._table.get_item(Key={"user_id": user_id})["Item"]
        return item
