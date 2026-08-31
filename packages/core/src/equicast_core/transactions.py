"""Class-based client for equicast's S3 JSON user-data store —
transactions domain.

Unlike every other Phase D domain (one JSON object per user), transactions
are stored **one JSON object per holding**, at
`transactions/<user_id>/<holding_id>.json`. Every real access pattern here
is already scoped to a single holding — filtering by `holding_id`, a
`SELL`'s cumulative-shares check, cascading a delete when a holding is
removed — so partitioning by holding_id means each of those touches
exactly one S3 object instead of the whole-user blob every other domain
rewrites on every write. The trade-off: `list_transactions` with no
`holding_id` filter (list *everything* for a user) has to enumerate and
read every holding's file instead of one read — see `_load_all` — which is
fine since that's the uncommon path and it's bounded by the user's
existing per-parent holding caps.

A transaction always hangs off exactly one holding — never an
account/pie/watchlist directly. Ownership of that holding, and whether
it's even eligible for transactions at all (fx holdings and watchlist
holdings aren't — see `backend/transactions/views.py`), isn't validated
here — `TransactionsClient` only knows about transactions, the same way
`PiesClient` leaves account_id ownership to the caller.

Every account has a `transaction_type` of `AVERAGE` or `TRANSACTION` (see
`AccountsClient`), and every holding under that account (directly, or via
one of its pies) records transactions in the matching shape — passed in
here as `mode` since resolving it requires reading the holding's account,
which is the caller's job, not this client's:

- `AVERAGE`: a single running snapshot per holding — `no_of_shares` and
  `average_price`, no `date`/`type`. Mutable via `update_transaction`,
  since it's a snapshot the user corrects over time rather than a log.
  `create_transaction` raises `TransactionAlreadyExistsError` for a second
  attempt against the same holding — use `update_transaction` instead.
- `TRANSACTION`: a log of discrete `BUY`/`SELL` events — `no_of_shares`,
  `price`, `date`, `type`, any number per holding (up to
  `max_transactions_for_holding`, `-1` for no cap — see the module-level
  default below). Immutable once created (no `update_transaction` —
  mirrors `HoldingsClient` treating a holding's identity fields as
  immutable); `create_transaction` raises `InsufficientSharesError` for a
  `SELL` whose quantity would take the holding's net shares (sum of prior
  `BUY`s minus prior `SELL`s, in whatever order they happen to have been
  recorded — not date-ordered) below zero.

Every record has the same stable shape regardless of mode (all six of
`no_of_shares`/`average_price`/`price`/`date`/`type` are always present,
`None` where not applicable) — the same "stable shape rather than
sometimes-absent keys" reasoning `HoldingsClient` uses for its three
parent-id fields. `list_transactions`'s `year`/`date_from`/`date_to`
filters only ever match `TRANSACTION`-mode records — an `AVERAGE` record's
`date` is always `None`, so it's excluded from any date-scoped query,
which is the correct behavior for a dateless snapshot rather than a bug.

For now this only stores what the caller gives it — no computed average
price, dividends, or returns.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import boto3

#: Default ceiling on transactions per holding, used when
#: `TransactionsClient` isn't given an explicit `max_transactions_for_holding`.
#: Overridable per deployment via the `MAX_TRANSACTIONS_FOR_HOLDING` env var
#: (see settings.py) rather than a code change — not a cost control, but a
#: safety limit: `create_transaction`/`update_transaction` still
#: read-modify-write one holding's whole file, so an unbounded
#: TRANSACTION-mode log — which only ever grows, never gets pruned —
#: degrades operations against that one holding over time. `-1` disables
#: the cap entirely for a deployment that wants no limit.
MAX_TRANSACTIONS_FOR_HOLDING = 500

#: Valid values for a TRANSACTION-mode record's `type`.
TRANSACTION_ACTIONS = {"BUY", "SELL"}

#: Bounds retries on a write losing the conditional-put race to a concurrent
#: writer (e.g. two browser tabs). Each retry re-reads the current state, so
#: this only loops when another write lands in the narrow window between
#: this client's own read and put.
_MAX_CONFLICT_RETRIES = 3


class TransactionLimitExceededError(Exception):
    """Raised by `create_transaction` when the target holding is already at
    max_transactions_for_holding transactions."""


class TransactionNotFoundError(Exception):
    """Raised by `get_transaction`/`update_transaction`/`delete_transaction`
    for an unknown transaction id."""


class TransactionAlreadyExistsError(Exception):
    """Raised by `create_transaction` for a second AVERAGE-mode record
    against the same holding — use `update_transaction` instead."""


class TransactionAmountError(Exception):
    """Raised when `no_of_shares`/`average_price`/`price` isn't a positive
    number, or `type` isn't one of `TRANSACTION_ACTIONS`."""


class InsufficientSharesError(Exception):
    """Raised by `create_transaction` for a `SELL` whose quantity would
    take the holding's net recorded shares below zero."""


def _validate_positive_amount(value: Any, field_name: str) -> Decimal:
    """Parse `value` (whatever JSON type the caller sent) via its string
    form rather than straight to `Decimal` — going through `float` first
    would round-trip through binary floating point before `Decimal` ever
    sees it, reintroducing the imprecision `Decimal` exists to avoid."""
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise TransactionAmountError(f"Invalid {field_name}: {value!r}.") from exc
    if amount <= 0:
        raise TransactionAmountError(f"{field_name} must be positive, got {value!r}.")
    return amount


class TransactionsClient:
    """Reads and writes one user's transactions as one JSON object per
    holding in S3 — see module docstring for why, unlike every other Phase
    D domain here, this isn't one object per user."""

    def __init__(
        self,
        bucket: str,
        s3_client: Any = None,
        region_name: str | None = None,
        max_transactions_for_holding: int = MAX_TRANSACTIONS_FOR_HOLDING,
    ) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)
        self._max_transactions_for_holding = max_transactions_for_holding

    @property
    def max_transactions_for_holding(self) -> int:
        return self._max_transactions_for_holding

    def _prefix(self, user_id: str) -> str:
        return f"transactions/{user_id}/"

    def _key(self, user_id: str, holding_id: str) -> str:
        return f"{self._prefix(user_id)}{holding_id}.json"

    def _load(self, user_id: str, holding_id: str) -> tuple[list[dict[str, Any]], str | None]:
        """Return `(transactions, etag)` for one holding. `etag` is `None`
        if this holding has no transactions object yet, so the next write
        knows to use `IfNoneMatch="*"` instead of `IfMatch` on a
        nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id, holding_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None
        body = json.loads(response["Body"].read())
        return body.get("transactions", []), response["ETag"]

    def _load_all(self, user_id: str) -> list[dict[str, Any]]:
        """Every transaction across all of the user's holdings — used only
        when `list_transactions` is called with no `holding_id` filter.
        O(holdings) S3 reads rather than the one-read-per-domain every
        other Phase D client gets, the cost of partitioning per holding_id
        instead of per user (see module docstring)."""
        transactions: list[dict[str, Any]] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix(user_id)):
            for obj in page.get("Contents", []):
                response = self._s3.get_object(Bucket=self._bucket, Key=obj["Key"])
                body = json.loads(response["Body"].read())
                transactions.extend(body.get("transactions", []))
        return transactions

    def _save(
        self,
        user_id: str,
        holding_id: str,
        transactions: list[dict[str, Any]],
        etag: str | None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id, holding_id),
            "Body": json.dumps({"transactions": transactions}).encode("utf-8"),
            "ContentType": "application/json",
        }
        if etag is None:
            kwargs["IfNoneMatch"] = "*"
        else:
            kwargs["IfMatch"] = etag
        self._s3.put_object(**kwargs)

    def _is_conflict(self, exc: Exception) -> bool:
        return getattr(exc, "response", {}).get("Error", {}).get("Code") == "PreconditionFailed"

    def list_transactions(
        self,
        user_id: str,
        holding_id: str | None = None,
        year: int | str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the user's transactions, optionally narrowed to one
        `holding_id` (a single-file read; omitting it reads every holding's
        file — see `_load_all`) and/or by `year` and/or an inclusive
        `date_from`/`date_to` range, matched against `date`
        ("YYYY-MM-DD", ISO strings sort/compare lexicographically). Since
        `AVERAGE`-mode records have no `date`, they never match a
        `year`/`date_from`/`date_to` filter."""
        if holding_id is not None:
            transactions, _ = self._load(user_id, holding_id)
        else:
            transactions = self._load_all(user_id)

        if year is not None:
            year_str = str(year)
            transactions = [
                t for t in transactions if t["date"] is not None and t["date"][:4] == year_str
            ]
        if date_from is not None:
            transactions = [
                t for t in transactions if t["date"] is not None and t["date"] >= date_from
            ]
        if date_to is not None:
            transactions = [
                t for t in transactions if t["date"] is not None and t["date"] <= date_to
            ]
        return transactions

    def get_transaction(self, user_id: str, holding_id: str, transaction_id: str) -> dict[str, Any]:
        """Return the transaction matching `transaction_id` within
        `holding_id`'s file, raising `TransactionNotFoundError` if no such
        transaction exists."""
        transactions, _ = self._load(user_id, holding_id)
        transaction = next((t for t in transactions if t["id"] == transaction_id), None)
        if transaction is None:
            raise TransactionNotFoundError(
                f"No transaction '{transaction_id}' for holding '{holding_id}'."
            )
        return transaction

    def create_transaction(
        self,
        user_id: str,
        holding_id: str,
        mode: str,
        *,
        no_of_shares: Any,
        average_price: Any = None,
        price: Any = None,
        date: str | None = None,
        type: str | None = None,
    ) -> dict[str, Any]:
        """Create a transaction against `holding_id`, shaped by `mode`
        (`"AVERAGE"` or `"TRANSACTION"` — resolved by the caller from the
        holding's account, see module docstring).

        Raises `TransactionAmountError` for a non-positive
        `no_of_shares`/`average_price`/`price`, or a `type` outside
        `TRANSACTION_ACTIONS`; `TransactionAlreadyExistsError` for a second
        `AVERAGE`-mode record against the same holding;
        `TransactionLimitExceededError` past `max_transactions_for_holding`;
        and `InsufficientSharesError` for a `SELL` that would take the
        holding's net recorded shares below zero.
        """
        if mode not in {"AVERAGE", "TRANSACTION"}:
            raise ValueError(f"Unknown mode: {mode!r}.")

        for _ in range(_MAX_CONFLICT_RETRIES):
            existing, etag = self._load(user_id, holding_id)

            shares = _validate_positive_amount(no_of_shares, "no_of_shares")
            if mode == "AVERAGE":
                if existing:
                    raise TransactionAlreadyExistsError(
                        f"Holding '{holding_id}' already has an AVERAGE record — "
                        "use update_transaction instead."
                    )
                _validate_positive_amount(average_price, "average_price")
            else:
                if type not in TRANSACTION_ACTIONS:
                    raise TransactionAmountError(f"Invalid type: {type!r}.")
                _validate_positive_amount(price, "price")
                if type == "SELL":
                    net = sum(
                        (
                            Decimal(str(t["no_of_shares"]))
                            if t["type"] == "BUY"
                            else -Decimal(str(t["no_of_shares"]))
                        )
                        for t in existing
                    )
                    if shares > net:
                        raise InsufficientSharesError(
                            f"Holding '{holding_id}' has {net} net shares recorded; "
                            f"cannot sell {shares}."
                        )

            if (
                self._max_transactions_for_holding != -1
                and len(existing) >= self._max_transactions_for_holding
            ):
                raise TransactionLimitExceededError(
                    f"Holding '{holding_id}' already has "
                    f"{self._max_transactions_for_holding} transactions."
                )

            now = datetime.now(UTC).isoformat()
            transaction = {
                "id": str(uuid.uuid4()),
                "holding_id": holding_id,
                "no_of_shares": no_of_shares,
                "average_price": average_price if mode == "AVERAGE" else None,
                "price": price if mode == "TRANSACTION" else None,
                "date": date if mode == "TRANSACTION" else None,
                "type": type if mode == "TRANSACTION" else None,
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._save(user_id, holding_id, [*existing, transaction], etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return transaction
        raise RuntimeError(
            f"Too many conflicting writes to transactions for holding '{holding_id}'."
        )

    def update_transaction(
        self, user_id: str, holding_id: str, transaction_id: str, **fields: Any
    ) -> dict[str, Any]:
        """Patch the AVERAGE-mode transaction matching `transaction_id`
        within `holding_id`'s file with `fields`
        (`no_of_shares`/`average_price`), raising `TransactionNotFoundError`
        if no such transaction exists, or `ValueError` if it's a
        TRANSACTION-mode record (immutable — mirrors
        `HoldingsClient.delete_holding` raising `ValueError` for a
        pie-scoped holding)."""
        if "no_of_shares" in fields:
            _validate_positive_amount(fields["no_of_shares"], "no_of_shares")
        if "average_price" in fields:
            _validate_positive_amount(fields["average_price"], "average_price")

        for _ in range(_MAX_CONFLICT_RETRIES):
            transactions, etag = self._load(user_id, holding_id)
            index = next((i for i, t in enumerate(transactions) if t["id"] == transaction_id), None)
            if index is None:
                raise TransactionNotFoundError(
                    f"No transaction '{transaction_id}' for holding '{holding_id}'."
                )
            if transactions[index]["type"] is not None:
                raise ValueError(
                    f"Transaction '{transaction_id}' is a TRANSACTION-mode record — immutable."
                )
            updated = {
                **transactions[index],
                **fields,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            transactions[index] = updated
            try:
                self._save(user_id, holding_id, transactions, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return updated
        raise RuntimeError(
            f"Too many conflicting writes to transactions for holding '{holding_id}'."
        )

    def delete_transaction(self, user_id: str, holding_id: str, transaction_id: str) -> None:
        """Remove the transaction matching `transaction_id` from
        `holding_id`'s file, raising `TransactionNotFoundError` if no such
        transaction exists."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            transactions, etag = self._load(user_id, holding_id)
            remaining = [t for t in transactions if t["id"] != transaction_id]
            if len(remaining) == len(transactions):
                raise TransactionNotFoundError(
                    f"No transaction '{transaction_id}' for holding '{holding_id}'."
                )
            try:
                self._save(user_id, holding_id, remaining, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(
            f"Too many conflicting writes to transactions for holding '{holding_id}'."
        )

    def has_transactions_for_holdings(self, user_id: str, holding_ids: list[str]) -> bool:
        """Whether any of `holding_ids` has at least one transaction
        recorded — a targeted existence check across just these holdings'
        files (short-circuiting on the first hit) rather than the full
        per-user scan `list_transactions()` with no filter would do. Backs
        accounts/views.py's transaction_type PATCH guard."""
        return any(self._load(user_id, holding_id)[0] for holding_id in holding_ids)

    def delete_transactions_for_holdings(self, user_id: str, holding_ids: list[str]) -> int:
        """Delete every transaction file in `holding_ids` outright (rather
        than rewriting each to an empty list), returning how many
        transaction records were removed in total. Backs holdings/views.py's
        delete and accounts/pies force-delete cascades — called once the
        holding itself is already gone, so there's no concurrent writer to
        race against and no conditional-write retry needed here, unlike
        every other method on this client."""
        removed = 0
        for holding_id in holding_ids:
            transactions, _ = self._load(user_id, holding_id)
            if not transactions:
                continue
            removed += len(transactions)
            self._s3.delete_object(Bucket=self._bucket, Key=self._key(user_id, holding_id))
        return removed
