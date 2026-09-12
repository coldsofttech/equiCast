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

#: Applied to a brand-new profile on first login. Governs how every holding
#: across every one of the user's accounts/pies records transactions — see
#: TransactionsClient. Previously an account-level field; moved here so a
#: user can't end up with holdings in different modes across accounts.
DEFAULT_TRANSACTION_TYPE = "AVERAGE"

#: Applied to a brand-new profile on first login. Currencies the frontend's
#: login-time FX warm-up pairs against `default_currency` (GitHub issue
#: #149) — pre-reads each pair's parquet file into MarketDataClient's
#: process-wide cache before the user reaches a transaction form, so its
#: own historical-rate lookup (get_fx_rate_on_date) is fast. User-editable
#: via Settings, not derived from the user's actual holdings — a holding
#: has no currency field of its own (only Account.currency, the account's
#: own wrapper currency, not a ticker's real native/trading currency).
DEFAULT_FX_WARMUP_CURRENCIES = ["GBP", "USD", "EUR"]


class UserProfileClient:
    """Reads and upserts items in one DynamoDB user-profiles table."""

    def __init__(
        self, table_name: str, resource: Any = None, region_name: str | None = None
    ) -> None:
        self._table_name = table_name
        self._resource = resource or boto3.resource("dynamodb", region_name=region_name)

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
        `default_currency=DEFAULT_CURRENCY`/`transaction_type=
        DEFAULT_TRANSACTION_TYPE`/`fx_warmup_currencies=
        DEFAULT_FX_WARMUP_CURRENCIES` if this is their first login — or,
        for an existing profile that predates one or more of
        `transaction_type`/`fx_warmup_currencies` (each introduced after
        `default_currency`), backfilling just the missing attribute(s)
        onto it.

        The create is a conditional put (`attribute_not_exists(user_id)`) so
        a concurrent first login can't clobber a profile the user has
        already started customizing — on that race, this re-fetches and
        returns the winning write instead of overwriting it."""
        response = self._table.get_item(Key={"user_id": user_id})
        item = response.get("Item")
        if item is not None:
            backfill = {
                attr: default
                for attr, default in (
                    ("transaction_type", DEFAULT_TRANSACTION_TYPE),
                    ("fx_warmup_currencies", DEFAULT_FX_WARMUP_CURRENCIES),
                )
                if attr not in item
            }
            if backfill:
                response = self._table.update_item(
                    Key={"user_id": user_id},
                    UpdateExpression="SET " + ", ".join(f"{attr} = :{attr}" for attr in backfill),
                    ExpressionAttributeValues={
                        f":{attr}": value for attr, value in backfill.items()
                    },
                    ReturnValues="ALL_NEW",
                )
                return dict(response["Attributes"])
            return item

        item = {
            "user_id": user_id,
            "default_currency": DEFAULT_CURRENCY,
            "transaction_type": DEFAULT_TRANSACTION_TYPE,
            "fx_warmup_currencies": DEFAULT_FX_WARMUP_CURRENCIES,
        }
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(user_id)",
            )
        except self._table.meta.client.exceptions.ConditionalCheckFailedException:
            return self._table.get_item(Key={"user_id": user_id})["Item"]
        return item

    def update_default_currency(self, user_id: str, default_currency: str) -> dict[str, Any]:
        """Set `user_id`'s default_currency, creating their profile first
        (get_or_create_profile) if this is called before their first login.

        Returns the full updated item (ReturnValues=ALL_NEW) rather than a
        synthesized dict, in case the profile ever grows other fields."""
        self.get_or_create_profile(user_id)
        response = self._table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET default_currency = :c",
            ExpressionAttributeValues={":c": default_currency},
            ReturnValues="ALL_NEW",
        )
        return dict(response["Attributes"])

    def update_transaction_type(self, user_id: str, transaction_type: str) -> dict[str, Any]:
        """Set `user_id`'s transaction_type, creating their profile first
        (get_or_create_profile) if this is called before their first login.

        Whether this is even allowed (it's locked once the user has any
        transaction recorded, across any holding) is the caller's job to
        check first — this client only knows about profiles, the same way
        `TransactionsClient` leaves holding ownership to its caller."""
        self.get_or_create_profile(user_id)
        response = self._table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET transaction_type = :t",
            ExpressionAttributeValues={":t": transaction_type},
            ReturnValues="ALL_NEW",
        )
        return dict(response["Attributes"])

    def update_fx_warmup_currencies(
        self, user_id: str, fx_warmup_currencies: list[str]
    ) -> dict[str, Any]:
        """Set `user_id`'s fx_warmup_currencies (GitHub issue #149 — the
        currencies the frontend's login-time FX warm-up pairs against
        `default_currency`), creating their profile first
        (get_or_create_profile) if this is called before their first
        login. Whether each entry is a supported currency code is the
        caller's job to check first — this client only knows about
        profiles, the same way `update_transaction_type` leaves the
        transaction_type/holding-eligibility check to its caller."""
        self.get_or_create_profile(user_id)
        response = self._table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET fx_warmup_currencies = :c",
            ExpressionAttributeValues={":c": fx_warmup_currencies},
            ReturnValues="ALL_NEW",
        )
        return dict(response["Attributes"])
