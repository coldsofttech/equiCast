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

The user has a single global `transaction_type` of `AVERAGE` or
`TRANSACTION` (see `UserProfileClient`) governing every holding across
every one of their accounts/pies — passed in here as `mode` since resolving
it is the caller's job, not this client's:

- `AVERAGE`: exactly one `BUY`-type position entry per holding —
  `no_of_shares`, `average_price_native`, `date` — mutable via
  `update_transaction` since it's a running snapshot the user corrects over
  time rather than a log entry. `create_transaction` raises
  `TransactionAlreadyExistsError` for a second `BUY` attempt against the
  same holding — use `update_transaction` instead. A legacy record
  predating this shape may still have `type` stored as `None`; treated
  identically to `"BUY"` everywhere in this client.
- `TRANSACTION`: a log of discrete `BUY`/`SELL` events — `no_of_shares`,
  `price_native`, `date`, `type` — any number per holding (up to
  `max_transactions_for_holding`, `-1` for no cap — see the module-level
  default below). Immutable once created (no `update_transaction` —
  mirrors `HoldingsClient` treating a holding's identity fields as
  immutable); `create_transaction` raises `InsufficientSharesError` for a
  `SELL` whose quantity would take the holding's net shares (sum of prior
  `BUY`s minus prior `SELL`s, in whatever order they happen to have been
  recorded — not date-ordered) below zero.

Regardless of mode, a holding may also carry any number of `DIVIDEND`-type
entries — `amount_native`/`amount` (total cash received, not per-share) and
`date`, no `no_of_shares`/`average_price_native`/`average_price`/
`price_native`/`price`. These don't affect a `SELL`'s net-shares check and
aren't capped by the one-`BUY`-per-holding rule that applies to `AVERAGE`
mode. Mutable via `update_transaction` the same as an `AVERAGE`-mode `BUY`
entry — a dividend is a user-recorded fact the user may need to correct,
not an executed trade.

Every monetary field comes in a native/converted pair: `average_price_native`/
`price_native`/`amount_native` are exactly what the caller passed in (the
holding's own native currency — an instrument's trading currency, or a
DIVIDEND's payout currency, same thing); `average_price`/`price`/`amount`
are that same figure converted to the user's `default_currency` (see
`UserProfileClient`) as of the transaction's `date`, using `fx_rate` — the
historical FX rate for that date and currency pair by default, or a
caller-supplied override (GitHub issue #149: the user can see and correct
the rate a transaction actually used). Resolving *that* conversion — the
user's `default_currency`, the holding's native currency, whether to
auto-resolve via `MarketDataClient.get_fx_rate_on_date` or use an
override, and the FX lookup itself — is entirely the caller's job
(`backend/transactions/views.py`), the same way `mode` resolution is;
`TransactionsClient` only ever stores whatever `fx_rate`/converted value
it's given, unconditionally (every type, not just BUY/SELL — see
`create_transaction`), `None` when the caller couldn't resolve one (e.g.
no FX pair published for that currency combination on that date) — a
transaction is still recorded in that case, just without a converted
figure.

Every record has the same stable shape regardless of mode/type (all
eleven of `no_of_shares`/`average_price_native`/`average_price`/
`price_native`/`price`/`amount_native`/`amount`/`fx_rate`/`date`/`type`
are always present, `None` where not applicable) — the same "stable shape
rather than sometimes-absent keys" reasoning `HoldingsClient` uses for its
three parent-id fields. `date` is mandatory on every record now — a
legacy `AVERAGE`-mode record predating this may still have `date: None`;
treated as "no date on record" rather than backfilled. `list_transactions`'s
`year`/`date_from`/`date_to` filters skip any record whose `date` is
`None`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
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

#: Valid values for a TRANSACTION-mode record's `type`. AVERAGE mode only
#: ever uses "BUY" (its one position entry) and "DIVIDEND".
TRANSACTION_ACTIONS = {"BUY", "SELL", "DIVIDEND"}

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
    """Raised by `create_transaction` for a second `BUY`-type record
    against an AVERAGE-mode holding (use `update_transaction` instead), or
    for a second transaction sharing an already-recorded `external_id` —
    the latter is the race-safe half of import dedup and
    `sync_dividends_for_holdings`'s own auto-created-payout dedup, see
    `create_transaction`'s docstring."""


class TransactionAmountError(Exception):
    """Raised when `no_of_shares`/`average_price`/`price`/`amount` isn't a
    positive number, or `type` isn't valid for the given mode."""


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


def _normalize(transaction: dict[str, Any]) -> dict[str, Any]:
    """Backfill keys introduced after a record may have already been
    written — `amount` (the `DIVIDEND` type), then the native/converted
    split (`average_price_native`/`price_native`/`amount_native`, plus
    `average_price`/`price`/`amount` becoming the converted figure instead
    of the native one) — onto a record loaded from S3 that predates them,
    so reads of old data don't `KeyError` on a new key. Same "stable shape"
    reasoning as the rest of this client, just applied retroactively at
    read time instead of a migration; a record from before the native/
    converted split has no way to know which currency its bare
    `average_price`/`price`/`amount` was actually in, so it's left exactly
    where it is (still under the now-"converted" key) rather than guessed
    at — only the newly-introduced native counterpart backfills to `None`."""
    transaction.setdefault("amount", None)
    transaction.setdefault("average_price_native", None)
    transaction.setdefault("price_native", None)
    transaction.setdefault("amount_native", None)
    transaction.setdefault("fx_rate", None)
    transaction.setdefault("external_id", None)
    return transaction


def _sum_dividends(transactions: list[dict[str, Any]]) -> tuple[float, float | None]:
    """Total dividend cash received as `(dividends_native, dividends)` —
    present in both `AVERAGE` and `TRANSACTION` mode alike (a dividend
    never affects shares/cost, see module docstring), so this is computed
    once and folded into both of `compute_holding_rollup`'s branches. Same
    legacy fallback as `average_price_native`/`average_price`: a record
    predating the native/converted split has `amount_native` backfilled to
    `None`, with the original value still sitting under the bare
    (now-"converted") `amount` key — treated as the native figure for such
    a record, but never as the converted one. `dividends` (the converted
    total) is `None` whenever any contributing record's own converted
    amount couldn't be resolved (see `resolve_converted_amounts` — same
    "None when unresolvable" contract `invested` uses) — a partial
    converted total would be misleading, not just incomplete."""
    total_native = Decimal(0)
    total_converted = Decimal(0)
    converted_known = True
    for record in transactions:
        if record["type"] != "DIVIDEND":
            continue
        is_legacy = record.get("amount_native") is None
        native_raw = record.get("amount") if is_legacy else record.get("amount_native")
        if native_raw is not None:
            total_native += Decimal(str(native_raw))
        converted_raw = None if is_legacy else record.get("amount")
        if converted_known and converted_raw is not None:
            total_converted += Decimal(str(converted_raw))
        else:
            converted_known = False
    return float(total_native), (float(total_converted) if converted_known else None)


def compute_holding_rollup(transactions: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    """Return `{no_of_shares, average_price_native, average_price,
    invested_native, invested, dividends_native, dividends}` for one
    holding's full transaction history — the position summary persisted
    onto the holding record itself (see
    `HoldingsClient.update_holding_financials`) so pages that just need
    "what does this holding look like right now" (the account/pie holdings
    list, HoldingTickerPage's stats) never have to re-fetch and re-derive it
    from every transaction on every read. Only `no_of_shares`/
    `average_price_native`/`average_price`/`invested_native`/`invested`/
    `dividends_native`/`dividends` are rolled up here — profit/loss depends
    on the *current* market price too, which moves daily independent of any
    transaction, so it's deliberately left for the caller to compute at
    read time from these figures plus a live price rather than persisted
    (it would otherwise go stale between trades). `dividends` (like
    `invested`) is `None` whenever any contributing dividend's own
    converted amount couldn't be resolved — see `_sum_dividends`.

    `AVERAGE` mode mirrors `TransactionsClient`'s own "at most one BUY
    position entry" invariant — that record's fields are the rollup
    outright. `TRANSACTION` mode derives a weighted-average cost basis
    across every BUY/SELL (same method a brokerage "average cost" statement
    uses): each BUY adds to the running cost at its own price, each SELL
    removes shares at the *current* running average cost (not FIFO lot
    tracking), tracked in parallel for both the native cost and its
    converted counterpart. `average_price`/`invested` (the converted
    figures) are `None` whenever any contributing BUY's own converted price
    couldn't be resolved (see `resolve_converted_amounts` — same "None when
    unresolvable" contract as everywhere else in this module) — a partial
    converted total would be misleading, not just incomplete.

    A record from before the native/converted split (see
    `equicast_core.transactions._normalize`) has its `_native` field
    backfilled to `None`, with the original value still sitting under the
    bare (now-"converted") key — before the split, that bare field *was*
    the native-currency price, there being no FX conversion feature yet.
    This treats that bare value as the native figure for such a record (the
    same reading `_normalize`'s own docstring gives it) rather than
    crashing on a `None`, but never as the *converted* figure — there's no
    way to know what currency it's actually in, so the converted rollup
    falls back to `None`/unresolvable for a holding with any such record,
    same as an unresolved FX rate would."""
    if mode == "AVERAGE":
        dividends_native, dividends = _sum_dividends(transactions)
        record = next((t for t in transactions if t["type"] in ("BUY", None)), None)
        if record is None:
            return {
                "no_of_shares": 0,
                "average_price_native": None,
                "average_price": None,
                "invested_native": 0,
                "invested": 0,
                "dividends_native": dividends_native,
                "dividends": dividends,
            }
        shares = Decimal(str(record["no_of_shares"]))
        is_legacy = record.get("average_price_native") is None
        native_raw = (
            record.get("average_price")
            if is_legacy else record.get("average_price_native")
        )
        avg_native = Decimal(str(native_raw)) if native_raw is not None else None
        avg_converted_raw = None if is_legacy else record.get("average_price")
        return {
            "no_of_shares": float(shares),
            "average_price_native": float(avg_native) if avg_native is not None else None,
            "average_price": float(avg_converted_raw) if avg_converted_raw is not None else None,
            "invested_native": float(shares * avg_native) if avg_native is not None else 0,
            "invested": (
                float(shares * Decimal(str(avg_converted_raw)))
                if avg_converted_raw is not None
                else None
            ),
            "dividends_native": dividends_native,
            "dividends": dividends,
        }

    sorted_records = sorted(
        (t for t in transactions if t["type"] in ("BUY", "SELL")), key=lambda t: t["date"] or ""
    )
    shares = Decimal(0)
    cost_native = Decimal(0)
    cost_converted = Decimal(0)
    converted_known = True
    for record in sorted_records:
        qty = Decimal(str(record["no_of_shares"]))
        if record["type"] == "BUY":
            is_legacy = record.get("price_native") is None
            native_raw = record.get("price") if is_legacy else record.get("price_native")
            price_native = Decimal(str(native_raw)) if native_raw is not None else Decimal(0)
            shares += qty
            cost_native += qty * price_native
            price_converted = None if is_legacy else record.get("price")
            if converted_known and price_converted is not None:
                cost_converted += qty * Decimal(str(price_converted))
            else:
                converted_known = False
        elif shares > 0:
            cost_per_share_native = cost_native / shares
            sold = min(qty, shares)
            cost_native -= sold * cost_per_share_native
            if converted_known:
                cost_converted -= sold * (cost_converted / shares)
            shares -= sold

    dividends_native, dividends = _sum_dividends(transactions)
    return {
        "no_of_shares": float(shares),
        "average_price_native": float(cost_native / shares) if shares > 0 else None,
        "average_price": float(cost_converted / shares) if shares > 0 and converted_known else None,
        "invested_native": float(cost_native) if shares > 0 else 0,
        "invested": (
            float(cost_converted)
            if shares > 0 and converted_known
            else (0 if shares == 0 else None)
        ),
        "dividends_native": dividends_native,
        "dividends": dividends,
    }


def _average_mode_shares_at(
    existing_transactions: list[dict[str, Any]],
) -> tuple[Callable[[str], Decimal] | None, str | None]:
    """Return `(shares_at, earliest_date)` for AVERAGE mode's single `BUY`
    (or legacy type-`None`) position entry — `shares_at` always returns
    that same fixed share count regardless of the date it's asked about,
    since AVERAGE mode has no `SELL` to have changed it since. `(None,
    None)` when there's no `BUY` on record yet — with no share count to
    anchor to, there's nothing reasonable to multiply a payout by."""
    buy = next((t for t in existing_transactions if t["type"] in ("BUY", None)), None)
    if buy is None or not buy.get("date") or not buy.get("no_of_shares"):
        return None, None
    shares = Decimal(str(buy["no_of_shares"]))
    return (lambda _ex_date: shares), buy["date"]


def _transaction_mode_shares_at(
    existing_transactions: list[dict[str, Any]],
) -> tuple[Callable[[str], Decimal] | None, str | None]:
    """Return `(shares_at, earliest_date)` for TRANSACTION mode's full
    `BUY`/`SELL` log — `shares_at(ex_date)` walks the same chronological
    running-total `compute_holding_rollup`'s `TRANSACTION`-mode branch
    uses (each `BUY` adds, each `SELL` subtracts, never below zero) and
    returns the balance as of the latest trade on or before `ex_date` —
    unlike AVERAGE mode, a payout's correct share count depends on
    *when* it was paid relative to every trade, not just the first one,
    since GitHub issue #124 wants TRANSACTION mode's dividends backfilled
    for the whole history, not just from "now" forward. `(None, None)`
    when there's no `BUY`/`SELL` on record yet."""
    trades = sorted(
        (t for t in existing_transactions if t["type"] in ("BUY", "SELL")),
        key=lambda t: t["date"] or "",
    )
    if not trades:
        return None, None

    timeline: list[tuple[str, Decimal]] = []
    running = Decimal(0)
    for trade in trades:
        qty = Decimal(str(trade["no_of_shares"]))
        running = running + qty if trade["type"] == "BUY" else max(running - qty, Decimal(0))
        timeline.append((trade["date"], running))

    def shares_at(ex_date: str) -> Decimal:
        shares = Decimal(0)
        for trade_date, running_shares in timeline:
            if trade_date > ex_date:
                break
            shares = running_shares
        return shares

    return shares_at, trades[0]["date"]


def compute_new_dividend_transactions(
    existing_transactions: list[dict[str, Any]],
    dividends: list[dict[str, Any]],
    synced_through: str | None = None,
    mode: str = "AVERAGE",
) -> list[dict[str, Any]]:
    """Return `[{date, amount_native}, ...]` for every `"paid"` entry in
    `dividends` (see `MarketDataClient.get_dividends`) not yet recorded
    against `existing_transactions` — the auto-dividend feature (AVERAGE
    mode: GitHub issue #123; TRANSACTION mode: issue #124): rather than
    requiring the user to hand-enter every payout, the caller (see
    `backend/transactions/views.py.sync_dividends_for_holdings`) turns each
    of these into a real `DIVIDEND` transaction via `create_transaction`.

    `mode` picks how many shares a payout is multiplied by —
    `_average_mode_shares_at` (a single fixed count from the one `BUY` on
    record) or `_transaction_mode_shares_at` (the running `BUY`/`SELL`
    balance as of that payout's own date, since TRANSACTION mode's full
    history means a payout years before "now" can still be backfilled
    correctly). `[]` whenever there's no position on record yet for that
    mode — with no share count to anchor to, there's nothing reasonable to
    multiply a payout by. A payout dated before the earliest trade is
    skipped outright, same "no way to add history from before there was
    anything held" reasoning either mode shares; in TRANSACTION mode a
    payout landing when the running balance is exactly zero (fully sold by
    then) is skipped too — nothing was held, so nothing was earned.

    `synced_through` (the holding's `dividends_synced_through` watermark —
    see `TransactionsClient.get_dividends_synced_through`/
    `latest_paid_dividend_date`) skips any payout on or before it
    regardless of whether it's still recorded — this is what makes
    deleting an auto-created `DIVIDEND` transaction a lasting correction
    rather than something the very next sync undoes: once a payout has
    been considered at all, it's never reconsidered, deleted or not. (A
    backdated `BUY`/`SELL` reopens part of that history instead of leaving
    it permanently skipped — see `TransactionsClient.
    rewind_dividends_synced_through`.) `existing_transactions`' own
    `DIVIDEND` dates are still checked too (`[]` if `synced_through` is
    `None`, e.g. before this holding's first sync ever ran) —
    belt-and-suspenders against a payout the user entered by hand before
    any sync watermark existed."""
    shares_at, earliest_date = (
        _average_mode_shares_at(existing_transactions)
        if mode == "AVERAGE"
        else _transaction_mode_shares_at(existing_transactions)
    )
    if shares_at is None or earliest_date is None:
        return []
    recorded_dates = {
        t["date"] for t in existing_transactions if t["type"] == "DIVIDEND" and t.get("date")
    }

    new_entries: list[dict[str, Any]] = []
    for dividend in dividends:
        if dividend.get("status") != "paid":
            continue
        ex_date = dividend.get("ex_dividend_date")
        per_share = dividend.get("price")
        if not ex_date or per_share is None:
            continue
        if ex_date < earliest_date or ex_date in recorded_dates:
            continue
        if synced_through is not None and ex_date <= synced_through:
            continue
        shares = shares_at(ex_date)
        if shares <= 0:
            continue
        new_entries.append(
            {"date": ex_date, "amount_native": float(shares * Decimal(str(per_share)))}
        )
    return new_entries


def latest_paid_dividend_date(dividends: list[dict[str, Any]], current: str | None) -> str | None:
    """Return the more recent of `current` and the latest `"paid"`
    `ex_dividend_date` in `dividends` — the new `dividends_synced_through`
    watermark `sync_dividends_for_holdings` (backend/transactions/views.py,
    GitHub issue #123) advances a holding to after every sync, via
    `TransactionsClient.advance_dividends_synced_through`. `None` when
    `dividends` has no dated `"paid"` entry and `current` is also `None`
    (this holding has never had a paid payout on record at all)."""
    paid_dates = [
        d["ex_dividend_date"]
        for d in dividends
        if d.get("status") == "paid" and d.get("ex_dividend_date")
    ]
    candidates = paid_dates + ([current] if current else [])
    return max(candidates) if candidates else None


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

    def _load(
        self, user_id: str, holding_id: str
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """Return `(transactions, dividends_synced_through, etag)` for one
        holding. `dividends_synced_through` is the AVERAGE-mode
        auto-dividend feature's high-water mark (GitHub issue #123 — see
        `get_dividends_synced_through`/`advance_dividends_synced_through`),
        `None` if it's never been set. `etag` is `None` if this holding has
        no transactions object yet, so the next write knows to use
        `IfNoneMatch="*"` instead of `IfMatch` on a nonexistent object."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=self._key(user_id, holding_id))
        except self._s3.exceptions.NoSuchKey:
            return [], None, None
        body = json.loads(response["Body"].read())
        return (
            [_normalize(t) for t in body.get("transactions", [])],
            body.get("dividends_synced_through"),
            response["ETag"],
        )

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
                transactions.extend(_normalize(t) for t in body.get("transactions", []))
        return transactions

    def _save(
        self,
        user_id: str,
        holding_id: str,
        transactions: list[dict[str, Any]],
        dividends_synced_through: str | None,
        etag: str | None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": self._key(user_id, holding_id),
            "Body": json.dumps(
                {
                    "transactions": transactions,
                    "dividends_synced_through": dividends_synced_through,
                }
            ).encode("utf-8"),
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
        ("YYYY-MM-DD", ISO strings sort/compare lexicographically). A
        legacy record predating the mandatory `date` field never matches
        a `year`/`date_from`/`date_to` filter."""
        if holding_id is not None:
            transactions, _, _ = self._load(user_id, holding_id)
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
        transactions, _, _ = self._load(user_id, holding_id)
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
        date: str,
        type: str,
        no_of_shares: Any = None,
        average_price_native: Any = None,
        average_price: Any = None,
        price_native: Any = None,
        price: Any = None,
        amount_native: Any = None,
        amount: Any = None,
        fx_rate: Any = None,
        external_id: Any = None,
    ) -> dict[str, Any]:
        """Create a transaction against `holding_id`, shaped by `mode`
        (`"AVERAGE"` or `"TRANSACTION"` — resolved by the caller from the
        user's profile, see module docstring) and `type` (`"BUY"` in either
        mode, `"SELL"` in `TRANSACTION` mode only, or `"DIVIDEND"` in
        either mode).

        `average_price`/`price`/`amount` are the *converted* (user's
        default-currency) counterpart of `average_price_native`/
        `price_native`/`amount_native` — already resolved by the caller
        (see module docstring); passed straight through as given, `None`
        included, with no validation here beyond what the `_native` value
        already got. `fx_rate` is the effective rate the caller used to
        resolve that conversion (auto-resolved or user-overridden — the
        caller's call, see module docstring) — stored unconditionally,
        regardless of `type`, unlike the other monetary fields above which
        are `None`'d out for the types they don't apply to. `external_id` is
        an opaque caller-supplied identifier (e.g. a broker's own row/order
        id from a transaction import, or `sync_dividends_for_holdings`'
        synthetic `f"dividend:{ex_dividend_date}"` for an auto-created
        payout) stored the same unconditional way as `fx_rate` — `None` for
        a hand-entered/API-created transaction. `update_transaction` never
        allows patching it, so once set it's immutable for the life of the
        record. Whenever it's given, this method itself guards against a
        second record ever sharing it — re-read fresh on every conflict-
        retry attempt (not just checked once up front), so two callers
        racing to create the same logical transaction concurrently (two
        browser tabs, or a frontend effect double-firing) can't both
        succeed: whichever loses the underlying write race sees the
        winner's record on its own retry and raises instead of creating a
        duplicate. Import dedup (skip a re-imported row whose `external_id`
        already exists) is the caller-side half of this — this method is
        what makes that check race-safe rather than just a best-effort
        pre-check.

        Raises `TransactionAmountError` for a missing `date`, a `type` not
        valid for `mode`, or a non-positive `no_of_shares`/
        `average_price_native`/`price_native`/`amount_native` (whichever
        `type` requires); `TransactionAlreadyExistsError` for a second
        `BUY` against an `AVERAGE`-mode holding (use `update_transaction`
        instead) or for a second transaction sharing an already-recorded
        `external_id`; `TransactionLimitExceededError` past
        `max_transactions_for_holding`; and `InsufficientSharesError` for a
        `SELL` that would take the holding's net recorded shares below
        zero.
        """
        if mode not in {"AVERAGE", "TRANSACTION"}:
            raise ValueError(f"Unknown mode: {mode!r}.")
        allowed_types = {"BUY", "DIVIDEND"} if mode == "AVERAGE" else TRANSACTION_ACTIONS
        if type not in allowed_types:
            raise TransactionAmountError(f"Invalid type '{type}' for {mode} mode.")
        if not date:
            raise TransactionAmountError("date is required.")
        if fx_rate is not None:
            _validate_positive_amount(fx_rate, "fx_rate")

        for _ in range(_MAX_CONFLICT_RETRIES):
            existing, dividends_synced_through, etag = self._load(user_id, holding_id)

            if external_id is not None and any(
                t.get("external_id") == external_id for t in existing
            ):
                raise TransactionAlreadyExistsError(
                    f"A transaction with external_id '{external_id}' already exists for "
                    f"holding '{holding_id}'."
                )

            shares = None
            if type == "DIVIDEND":
                _validate_positive_amount(amount_native, "amount_native")
            else:
                shares = _validate_positive_amount(no_of_shares, "no_of_shares")
                if mode == "AVERAGE":
                    if any(t["type"] in ("BUY", None) for t in existing):
                        raise TransactionAlreadyExistsError(
                            f"Holding '{holding_id}' already has a BUY record — "
                            "use update_transaction instead."
                        )
                    _validate_positive_amount(average_price_native, "average_price_native")
                else:
                    _validate_positive_amount(price_native, "price_native")
                    if type == "SELL":
                        net = sum(
                            (
                                Decimal(str(t["no_of_shares"]))
                                if t["type"] == "BUY"
                                else -Decimal(str(t["no_of_shares"]))
                            )
                            for t in existing
                            if t["type"] in ("BUY", "SELL")
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
            is_average_buy = mode == "AVERAGE" and type == "BUY"
            is_transaction_trade = mode == "TRANSACTION" and type in ("BUY", "SELL")
            transaction = {
                "id": str(uuid.uuid4()),
                "holding_id": holding_id,
                "no_of_shares": no_of_shares if type != "DIVIDEND" else None,
                "average_price_native": average_price_native if is_average_buy else None,
                "average_price": average_price if is_average_buy else None,
                "price_native": price_native if is_transaction_trade else None,
                "price": price if is_transaction_trade else None,
                "amount_native": amount_native if type == "DIVIDEND" else None,
                "amount": amount if type == "DIVIDEND" else None,
                "fx_rate": fx_rate,
                "external_id": external_id,
                "date": date,
                "type": type,
                "created_at": now,
                "updated_at": now,
            }
            try:
                self._save(
                    user_id, holding_id, [*existing, transaction], dividends_synced_through, etag
                )
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return transaction
        raise RuntimeError(
            f"Too many conflicting writes to transactions for holding '{holding_id}'."
        )

    def update_transaction(
        self, user_id: str, holding_id: str, transaction_id: str, mode: str, **fields: Any
    ) -> dict[str, Any]:
        """Patch the transaction matching `transaction_id` within
        `holding_id`'s file with `fields`, raising `TransactionNotFoundError`
        if no such transaction exists, or `ValueError` if it's an immutable
        TRANSACTION-mode `BUY`/`SELL` record (mirrors
        `HoldingsClient.delete_holding` raising `ValueError` for a
        pie-scoped holding), or if `fields` carries a key that doesn't
        apply to the record's type.

        Mutable records are an AVERAGE-mode `BUY` (position entry —
        `no_of_shares`/`average_price_native`/`average_price`/`fx_rate`/
        `date`) or any `DIVIDEND` entry in either mode
        (`amount_native`/`amount`/`fx_rate`/`date`) — see module docstring
        for why a dividend is mutable regardless of mode, and for the
        native/converted split (`average_price`/`amount` here are the
        already-resolved converted figures — the caller recomputes them
        from the patched native value/date/`fx_rate` and passes them all
        in together, the same as `create_transaction`). `external_id` is
        deliberately absent from both allowed sets — it's immutable once set
        by `create_transaction`, so an import's dedup check can always trust
        it against the original import rather than a value that could have
        drifted since.

        Patching an AVERAGE-mode `BUY`'s `date` or `no_of_shares` drops
        every auto-created `DIVIDEND` on file and rewinds
        `dividends_synced_through` to `None`, so the next
        `sync_dividends_for_holdings` (backend/transactions/views.py)
        rebuilds the whole dividend history fresh against the updated
        anchor/share count instead of leaving stale amounts (computed
        against the old share count) or a gap of newly-eligible payouts a
        backdated `date` opened up but the old watermark had already
        skipped past. This also un-does any dividend the user previously
        deleted by hand or edited — same tradeoff as the module docstring's
        "only future, not past" reasoning: an edit here is treated as a
        correction significant enough to re-derive everything from, not a
        surgical patch."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            transactions, dividends_synced_through, etag = self._load(user_id, holding_id)
            index = next((i for i, t in enumerate(transactions) if t["id"] == transaction_id), None)
            if index is None:
                raise TransactionNotFoundError(
                    f"No transaction '{transaction_id}' for holding '{holding_id}'."
                )
            record_type = transactions[index]["type"]
            if record_type == "DIVIDEND":
                allowed = {"date", "amount_native", "amount", "fx_rate"}
            elif mode == "AVERAGE" and record_type in ("BUY", None):
                allowed = {
                    "date",
                    "no_of_shares",
                    "average_price_native",
                    "average_price",
                    "fx_rate",
                }
            else:
                raise ValueError(
                    f"Transaction '{transaction_id}' is a TRANSACTION-mode BUY/SELL record — "
                    "immutable."
                )
            disallowed = fields.keys() - allowed
            if disallowed:
                raise ValueError(
                    f"Field(s) not applicable to this record: {', '.join(sorted(disallowed))}."
                )
            if "no_of_shares" in fields:
                _validate_positive_amount(fields["no_of_shares"], "no_of_shares")
            if "average_price_native" in fields:
                _validate_positive_amount(fields["average_price_native"], "average_price_native")
            if "amount_native" in fields:
                _validate_positive_amount(fields["amount_native"], "amount_native")
            if fields.get("fx_rate") is not None:
                _validate_positive_amount(fields["fx_rate"], "fx_rate")

            updated = {
                **transactions[index],
                **fields,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            transactions[index] = updated
            if mode == "AVERAGE" and record_type in ("BUY", None) and (
                "date" in fields or "no_of_shares" in fields
            ):
                transactions = [t for t in transactions if t["type"] != "DIVIDEND"]
                dividends_synced_through = None
            try:
                self._save(user_id, holding_id, transactions, dividends_synced_through, etag)
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
        transaction exists.

        Deliberately leaves `dividends_synced_through` untouched — deleting
        a `DIVIDEND` transaction that the AVERAGE-mode auto-dividend
        feature (GitHub issue #123) created must not make that payout look
        unsynced again, or the very next `GET /api/accounts/`/`/api/pies/`/
        `/api/holdings/` would just recreate it (see
        `sync_dividends_for_holdings`, backend/transactions/views.py) —
        deleting is meant to be a lasting correction, undone only by the
        user re-adding it by hand."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            transactions, dividends_synced_through, etag = self._load(user_id, holding_id)
            remaining = [t for t in transactions if t["id"] != transaction_id]
            if len(remaining) == len(transactions):
                raise TransactionNotFoundError(
                    f"No transaction '{transaction_id}' for holding '{holding_id}'."
                )
            try:
                self._save(user_id, holding_id, remaining, dividends_synced_through, etag)
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
        identity/views.py's transaction_type PATCH guard."""
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
            transactions, _, _ = self._load(user_id, holding_id)
            if not transactions:
                continue
            removed += len(transactions)
            self._s3.delete_object(Bucket=self._bucket, Key=self._key(user_id, holding_id))
        return removed

    def get_dividends_synced_through(self, user_id: str, holding_id: str) -> str | None:
        """Return `holding_id`'s `dividends_synced_through` watermark (see
        `_load`), `None` if it's never been set — read by
        `sync_dividends_for_holdings` (backend/transactions/views.py) before
        deciding which paid payouts (GitHub issue #123) still need
        creating."""
        return self._load(user_id, holding_id)[1]

    def advance_dividends_synced_through(
        self, user_id: str, holding_id: str, through_date: str
    ) -> None:
        """Raise `holding_id`'s `dividends_synced_through` watermark to
        `through_date` if it's more recent than what's on record (a no-op
        otherwise — `through_date` arrives from
        `latest_paid_dividend_date`, which already folds in the existing
        watermark, so this is only ever a no-op when nothing changed
        between load and here). Called once per holding after
        `sync_dividends_for_holdings` finishes creating whatever new
        `DIVIDEND` transactions a sync turned up, so a payout already
        considered — created, or skipped as pre-`BUY` — is never
        re-examined even after the user deletes the resulting transaction
        (see `delete_transaction`)."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            transactions, current, etag = self._load(user_id, holding_id)
            if current is not None and current >= through_date:
                return
            try:
                self._save(user_id, holding_id, transactions, through_date, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(
            f"Too many conflicting writes to transactions for holding '{holding_id}'."
        )

    def rewind_dividends_synced_through(
        self, user_id: str, holding_id: str, transaction_date: str
    ) -> None:
        """Clear `holding_id`'s `dividends_synced_through` watermark (see
        `advance_dividends_synced_through`) and drop every auto-created
        `DIVIDEND` on file, if `transaction_date` falls on or before the
        watermark — TRANSACTION mode's auto-dividend feature (GitHub issue
        #124): a `BUY`/`SELL` just created or deleted somewhere inside the
        range a sync has already examined changes the running share-count
        timeline `compute_new_dividend_transactions` uses for every payout
        after it, so an already-created `DIVIDEND`'s amount (computed
        against the *old* timeline) is now stale, not just newly-eligible
        payouts the old timeline had skipped. Dropping every `DIVIDEND`
        clears `compute_new_dividend_transactions`' `recorded_dates` dedup
        too, so the next `sync_dividends_for_holdings` run rebuilds the
        holding's whole paid-dividend history fresh against the corrected
        timeline, same tradeoff `TransactionsClient.update_transaction`
        makes for an AVERAGE-mode `BUY` edit — this also un-does any
        dividend the user previously edited or deleted by hand. A no-op
        when the watermark is unset or already before `transaction_date`
        (an ordinary new-today `BUY`/`SELL`, not a backdated correction) —
        nothing already-examined needs rechecking. Called from
        `TransactionListView.post`/`TransactionDetailView.delete`
        (backend/transactions/views.py) for a TRANSACTION-mode `BUY`/`SELL`
        only — AVERAGE mode has no `SELL`, and its one `BUY` can't be
        created a second time."""
        for _ in range(_MAX_CONFLICT_RETRIES):
            transactions, current, etag = self._load(user_id, holding_id)
            if current is None or transaction_date > current:
                return
            transactions = [t for t in transactions if t["type"] != "DIVIDEND"]
            try:
                self._save(user_id, holding_id, transactions, None, etag)
            except self._s3.exceptions.ClientError as exc:
                if self._is_conflict(exc):
                    continue
                raise
            return
        raise RuntimeError(
            f"Too many conflicting writes to transactions for holding '{holding_id}'."
        )
