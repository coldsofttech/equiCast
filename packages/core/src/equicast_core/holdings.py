"""Class-based client for equicast's S3 JSON user-data store — holdings
domain.

Same shape as `PiesClient`/`WatchlistsClient`: each user's holdings live as
a single JSON object at `holdings/<user_id>.json`, reads/writes use S3
conditional requests for optimistic concurrency, and a write that loses the
conditional-put race is retried against the now-current state.

A holding hangs off exactly one parent — an account (`account_id`), a pie
(`pie_id`), or a watchlist (`watchlist_id`); the other two parent fields are
always `None` (a stable shape rather than sometimes-absent keys). Ticker/
asset_class existence against equicast-market-data-* isn't validated here —
the caller (the Django view) does that via `MarketDataClient`, the same way
`PiesClient` leaves account_id ownership to the view.

A pie holding also carries `allocation_pct` — the only parent type with an
allocation concept, since a pie represents a 100%-allocated slice of an
account. Pie holdings are never created/removed/reallocated one at a time —
an independent single-item write can't keep a pie's percentages summing to
exactly 100 once it already holds anything — `sync_pie_holdings` applies an
add/remove/reallocate batch atomically instead. Account-direct and
watchlist holdings have no allocation concept and go through the plain
`create_holding`/`delete_holding`.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import boto3

#: Default per-parent caps, used when `HoldingsClient` isn't given explicit
#: constructor overrides. Overridable per deployment via the
#: MAX_HOLDINGS_FOR_ACCOUNT/_PIE/_WATCHLIST env vars (see settings.py)
#: rather than a code change, so product can tune each cap without a
#: release.
MAX_HOLDINGS_FOR_ACCOUNT = 100
MAX_HOLDINGS_FOR_PIE = 50
MAX_HOLDINGS_FOR_WATCHLIST = 20

#: The exact total `allocation_pct` must sum to across a pie's holdings,
#: once it holds at least one — see `sync_pie_holdings`.
_FULL_ALLOCATION = Decimal("100")

#: Bounds retries on a write losing the conditional-put race to a concurrent
#: writer (e.g. two browser tabs). Each retry re-reads the current state, so
#: this only loops when another write lands in the narrow window between
#: this client's own read and put.
_MAX_CONFLICT_RETRIES = 3


class HoldingLimitExceededError(Exception):
    """Raised by `create_holding`/`sync_pie_holdings` when the target
    parent is already at its cap of holdings."""


class HoldingAlreadyExistsError(Exception):
    """Raised by `create_holding`/`sync_pie_holdings` when the target
    parent already holds this ticker."""


class HoldingNotFoundError(Exception):
    """Raised by `get_holding`/`delete_holding` for an unknown holding id,
    and by `sync_pie_holdings` for a `remove`/`reallocate` id that isn't
    actually one of the pie's holdings."""


class AllocationError(Exception):
    """Raised by `sync_pie_holdings` when an `allocation_pct` isn't a
    positive number, or the resulting non-empty holdings wouldn't sum to
    exactly 100%."""


def _validate_allocation(value: Any) -> Decimal:
    """Parse `value` (whatever JSON type the caller sent) via its string
    form rather than straight to `Decimal` — going through `float` first
    would round-trip through binary floating point before `Decimal` ever
    sees it, reintroducing the imprecision `Decimal` exists to avoid."""
    try:
        pct = Decimal(str(value))
    except InvalidOperation as exc:
        raise AllocationError(f"Invalid allocation_pct: {value!r}.") from exc
    if pct <= 0:
        raise AllocationError(f"allocation_pct must be positive, got {value!r}.")
    return pct


class HoldingsClient:
    """Reads and writes one user's holdings as a JSON object in S3."""

    def __init__(
        self,
        bucket: str,
        s3_client: Any = None,
        region_name: str | None = None,
        max_holdings_for_account: int = MAX_HOLDINGS_FOR_ACCOUNT,
        max_holdings_for_pie: int = MAX_HOLDINGS_FOR_PIE,
        max_holdings_for_watchlist: int = MAX_HOLDINGS_FOR_WATCHLIST,
    ) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)
        self._max_holdings_for_account = max_holdings_for_account
        self._max_holdings_for_pie = max_holdings_for_pie
        self._max_holdings_for_watchlist = max_holdings_for_watchlist

    @property
    def max_holdings_for_account(self) -> int:
        return self._max_holdings_for_account

    @property
    def max_holdings_for_pie(self) -> int:
        return self._max_holdings_for_pie

    @property
    def max_holdings_for_watchlist(self) -> int:
        return self._max_holdings_for_watchlist

    def _key(self, user_id: str) -> str:
        return f"holdings/{user_id}.json"

    def _load(self, user_id: str) -> tuple[list[dict[str, Any]], str | None]:
        """Return `(holdings, etag)`. `etag` is `None` if the user has no
        holdings object yet, so the next write knows to use
        `IfNoneMatch="*"` instead of `IfMatch` on a nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None
        body = json.loads(response["Body"].read())
        return body.get("holdings", []), response["ETag"]

    def _save(self, user_id: str, holdings: list[dict[str, Any]], etag: str | None) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id),
            "Body": json.dumps({"holdings": holdings}).encode("utf-8"),
            "ContentType": "application/json",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        self._s3.put_object(**kwargs)

    def _is_conflict(self, exc: Exception) -> bool:
        return getattr(exc, "response", {}).get("Error", {}).get("Code") == "PreconditionFailed"

    def list_holdings(
        self,
        user_id: str,
        account_id: str | None = None,
        pie_id: str | None = None,
        watchlist_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the user's holdings, optionally narrowed to one parent.
        With no filter, returns every holding across all three parent
        types."""
        holdings, _ = self._load(user_id)
        if account_id is not None:
            holdings = [h for h in holdings if h["account_id"] == account_id]
        if pie_id is not None:
            holdings = [h for h in holdings if h["pie_id"] == pie_id]
        if watchlist_id is not None:
            holdings = [h for h in holdings if h["watchlist_id"] == watchlist_id]
        return holdings

    def get_holding(self, user_id: str, holding_id: str) -> dict[str, Any]:
        """Return the holding matching `holding_id`, raising
        `HoldingNotFoundError` if no such holding exists."""
        holdings, _ = self._load(user_id)
        holding = next((h for h in holdings if h["id"] == holding_id), None)
        if holding is None:
            raise HoldingNotFoundError(f"No holding '{holding_id}' for user '{user_id}'.")
        return holding

    def create_holding(
        self,
        user_id: str,
        ticker: str,
        asset_class: str,
        *,
        account_id: str | None = None,
        watchlist_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a holding directly under `account_id` or `watchlist_id`
        (exactly one of the two — pie-scoped holdings go through
        `sync_pie_holdings` instead, not this method)."""
        if (account_id is None) == (watchlist_id is None):
            raise ValueError("Exactly one of account_id/watchlist_id is required.")
        cap = (
            self._max_holdings_for_account
            if account_id is not None
            else self._max_holdings_for_watchlist
        )

        for _ in range(_MAX_CONFLICT_RETRIES):
            holdings, etag = self._load(user_id)
            scoped = [
                h
                for h in holdings
                if h["account_id"] == account_id and h["watchlist_id"] == watchlist_id
            ]
            if any(h["ticker"] == ticker for h in scoped):
                raise HoldingAlreadyExistsError(
                    f"Ticker '{ticker}' is already held here for user '{user_id}'."
                )
            if len(scoped) >= cap:
                raise HoldingLimitExceededError(f"Already at {cap} holdings here.")

            holding = {
                "id": str(uuid.uuid4()),
                "ticker": ticker,
                "asset_class": asset_class,
                "account_id": account_id,
                "pie_id": None,
                "watchlist_id": watchlist_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            try:
                self._save(user_id, [*holdings, holding], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return holding
        raise RuntimeError(f"Too many conflicting writes to holdings for user '{user_id}'.")

    def delete_holding(self, user_id: str, holding_id: str) -> None:
        """Remove the holding matching `holding_id`, raising
        `HoldingNotFoundError` if no such holding exists, or `ValueError`
        if it's pie-scoped (use `sync_pie_holdings` for those instead — a
        standalone delete can't keep the pie's allocations at 100%)."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            holdings, etag = self._load(user_id)
            target = next((h for h in holdings if h["id"] == holding_id), None)
            if target is None:
                raise HoldingNotFoundError(f"No holding '{holding_id}' for user '{user_id}'.")
            if target["pie_id"] is not None:
                raise ValueError(f"Holding '{holding_id}' is pie-scoped — use sync_pie_holdings.")
            remaining = [h for h in holdings if h["id"] != holding_id]
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(f"Too many conflicting writes to holdings for user '{user_id}'.")

    def delete_holdings_for_account(self, user_id: str, account_id: str) -> int:
        """Remove every direct-account holding under `account_id` (not
        pie-scoped ones — those live under the account's pies and are
        handled by `delete_holdings_for_pies`) in one write, returning how
        many were removed. Backs accounts/views.py's force delete; an empty
        match is a legitimate no-op, not an error, mirroring
        `PiesClient.delete_pies_for_account`."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            holdings, etag = self._load(user_id)
            remaining = [h for h in holdings if h["account_id"] != account_id]
            removed = len(holdings) - len(remaining)
            if removed == 0:
                return 0
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return removed
        raise RuntimeError(f"Too many conflicting writes to holdings for user '{user_id}'.")

    def delete_holdings_for_pies(self, user_id: str, pie_ids: list[str]) -> int:
        """Remove every holding whose pie_id is in `pie_ids`, in one write,
        returning how many were removed. Backs pies/views.py's force delete
        for a single pie (called with a one-element list) and
        accounts/views.py's force delete cascading through every pie under
        the account (called with the full list) — plural so an account
        with several pies removes all of their holdings in one write rather
        than one conditional-write round trip per pie."""
        pie_id_set = set(pie_ids)
        for _ in range(_MAX_CONFLICT_RETRIES):
            holdings, etag = self._load(user_id)
            remaining = [h for h in holdings if h["pie_id"] not in pie_id_set]
            removed = len(holdings) - len(remaining)
            if removed == 0:
                return 0
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return removed
        raise RuntimeError(f"Too many conflicting writes to holdings for user '{user_id}'.")

    def delete_holdings_for_watchlist(self, user_id: str, watchlist_id: str) -> int:
        """Remove every holding under `watchlist_id` in one write, returning
        how many were removed. Backs watchlists/views.py's force delete."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            holdings, etag = self._load(user_id)
            remaining = [h for h in holdings if h["watchlist_id"] != watchlist_id]
            removed = len(holdings) - len(remaining)
            if removed == 0:
                return 0
            try:
                self._save(user_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return removed
        raise RuntimeError(f"Too many conflicting writes to holdings for user '{user_id}'.")

    def sync_pie_holdings(
        self,
        user_id: str,
        pie_id: str,
        *,
        add: list[dict[str, Any]] | None = None,
        remove: list[str] | None = None,
        reallocate: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply an add/remove/reallocate batch to one pie's holdings
        atomically — every change is validated against the resulting state
        before anything is written, and either the whole batch lands in one
        write or none of it does.

        `add`: `[{"ticker", "asset_class", "allocation_pct"}, ...]`
        `remove`: `[holding_id, ...]`
        `reallocate`: `[{"id", "allocation_pct"}, ...]`

        Raises `HoldingNotFoundError` if a `remove`/`reallocate` id isn't
        one of this pie's holdings, `HoldingAlreadyExistsError` for a
        ticker already held in this pie (existing or duplicated within
        `add`), `HoldingLimitExceededError` past `max_holdings_for_pie`,
        and `AllocationError` if an `allocation_pct` isn't positive or the
        resulting holdings (when left non-empty) don't sum to exactly 100%.
        An empty result (every holding removed) is a valid, unconstrained
        state — the 100%-sum rule only applies once the pie holds anything.
        """
        add = add or []
        remove_ids = set(remove or [])
        reallocate_by_id = {entry["id"]: entry["allocation_pct"] for entry in (reallocate or [])}

        for _ in range(_MAX_CONFLICT_RETRIES):
            holdings, etag = self._load(user_id)
            others = [h for h in holdings if h["pie_id"] != pie_id]
            existing = [h for h in holdings if h["pie_id"] == pie_id]
            existing_ids = {h["id"] for h in existing}

            for holding_id in remove_ids | reallocate_by_id.keys():
                if holding_id not in existing_ids:
                    raise HoldingNotFoundError(
                        f"No holding '{holding_id}' in pie '{pie_id}' for user '{user_id}'."
                    )

            kept = []
            for holding in existing:
                if holding["id"] in remove_ids:
                    continue
                if holding["id"] in reallocate_by_id:
                    pct = reallocate_by_id[holding["id"]]
                    _validate_allocation(pct)
                    holding = {**holding, "allocation_pct": pct}
                kept.append(holding)

            kept_tickers = {h["ticker"] for h in kept}
            added: list[dict[str, Any]] = []
            for entry in add:
                ticker = entry["ticker"]
                if ticker in kept_tickers or ticker in {a["ticker"] for a in added}:
                    raise HoldingAlreadyExistsError(
                        f"Ticker '{ticker}' is already held in pie '{pie_id}'."
                    )
                _validate_allocation(entry["allocation_pct"])
                added.append(
                    {
                        "id": str(uuid.uuid4()),
                        "ticker": ticker,
                        "asset_class": entry["asset_class"],
                        "account_id": None,
                        "pie_id": pie_id,
                        "watchlist_id": None,
                        "allocation_pct": entry["allocation_pct"],
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

            final = kept + added
            if len(final) > self._max_holdings_for_pie:
                raise HoldingLimitExceededError(
                    f"Pie '{pie_id}' would exceed {self._max_holdings_for_pie} holdings."
                )
            if final:
                total = sum(_validate_allocation(h["allocation_pct"]) for h in final)
                if total != _FULL_ALLOCATION:
                    raise AllocationError(
                        f"Pie '{pie_id}' holdings must sum to exactly 100% (got {total})."
                    )

            try:
                self._save(user_id, [*others, *final], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return final
        raise RuntimeError(f"Too many conflicting writes to holdings for user '{user_id}'.")
