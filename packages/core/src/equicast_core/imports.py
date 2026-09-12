"""equicast-core: transaction-import parsing — CSV (a generic equicast
schema, plus broker-specific presets such as Trading 212) parsed into a
stable `ParsedRow` shape a caller (backend/transactions/import_views.py)
validates, resolves against the market-data catalog, and hands to
`equicast_core.transactions.TransactionsClient.create_transaction`.

Deliberately pure and stateless: every parser here takes a file-like object
and returns a `ParseResult`, or raises `ImportParseError` — no S3, no
network, no persistence, so nothing in this module needs mocking to test.

Only BUY/SELL rows are ever yielded. Dividend/interest/other non-trade rows
(a broker export typically has all of these mixed together) are dropped at
parse time, not downstream — equicast already auto-backfills DIVIDEND
transactions once a BUY/SELL position exists (see
`equicast_core.transactions.compute_new_dividend_transactions`), so
importing a broker's own dividend rows would double-count them.

A row that reads as a BUY/SELL action but carries unusable data (most
commonly a non-positive price — Trading 212 reports a fractional share
cashed out after a corporate action, e.g. a post-acquisition ISIN swap or a
stock split, as a real `Market sell` with `Price / share` of `0E-10`) is
never allowed to abort parsing the rest of the file — it's collected as an
`InvalidRow` instead, so one bad row out of thousands doesn't cost the user
their whole import. Only a structural problem with the file itself (a
required column missing entirely) raises `ImportParseError` and aborts the
whole parse — that's a wrong-preset/wrong-file situation, not a row-level
one. Corporate-action row types (stock splits, spin-offs, stock
acquisitions/ISIN changes, share-based dividends) are recognized-but-
not-trades today — silently dropped, counted in `rows_skipped` — rather
than actually modeled; see the transaction-import follow-up GitHub issues
for each.

`ParsedRow.fx_rate` is always in equicast's own native->default direction
(`converted = native * fx_rate` — see
`equicast_core.transactions.resolve_converted_amounts`), ready to pass
straight through as a caller's `fx_rate` override, regardless of which
direction the source file itself quotes a rate in. Trading 212's own
`Exchange rate` column is quoted default->native — the same "£1 = $1.34"
direction brokerage apps quote a rate in for a human to read (matching
equicast's own UI convention for a hand-entered override — see
`frontend/src/pages/holdings/HoldingTransactionsSection.jsx`'s
`TransactionForm`) — so `parse_trading212_csv` inverts it (`1 / rate`)
before it ever reaches a `ParsedRow`. Getting this backwards silently
produces a converted figure off by a factor of `rate²` instead of an
outright error, which is why it's handled once here rather than trusted to
each caller.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import IO, Any


class ImportParseError(Exception):
    """Raised by a preset parser for a missing/unrecognized column header,
    or a row whose required fields don't parse as expected. Never raised
    for a business-rule violation (insufficient shares, an unresolvable
    ticker, a disallowed type for the user's mode, ...) — those are the
    caller's job at preview/commit time, the same division of
    responsibility `TransactionsClient` uses for its own callers."""


@dataclass(frozen=True)
class ParsedRow:
    """One BUY/SELL row extracted from an imported file. Shaped close to
    `TransactionsClient.create_transaction`'s keyword arguments, but not
    identical — this also carries `asset_class`/`isin`/`name`/`raw`, which
    the import preview/commit views need for ticker resolution and display
    but `create_transaction` doesn't take.

    `external_id` is the source's own row/order id when it provides one
    (Trading 212's `ID` column) — `None` for the generic preset unless the
    user's own file supplies one; used for import dedup (see
    `TransactionsClient.create_transaction`'s `external_id` parameter).
    `fx_rate` is the source's own per-row exchange rate when provided —
    `None` when it doesn't carry one, in which case the caller falls back
    to equicast's own historical FX lookup (same "`None` means unresolved,
    caller decides what to do" contract used throughout this package).
    `asset_class` is `None` when the source doesn't distinguish one (e.g.
    Trading 212 rows) — left for the caller to resolve against the market
    data catalog."""

    external_id: str | None
    date: str  # "YYYY-MM-DD"
    type: str  # "BUY" | "SELL" only — never "DIVIDEND", see module docstring
    ticker: str
    asset_class: str | None
    isin: str | None
    name: str | None
    no_of_shares: float
    price_native: float
    currency: str | None
    fx_rate: float | None
    raw: dict[str, str]


@dataclass(frozen=True)
class InvalidRow:
    """One row that read as a BUY/SELL action but had data that couldn't be
    turned into a `ParsedRow` (most commonly a non-positive price/share
    count — see module docstring) — collected instead of aborting the rest
    of the file, and instead of being silently folded into
    `ParseResult.rows_skipped` (which means something different: a row that
    was never a trade attempt in the first place, e.g. a dividend)."""

    row_number: int
    ticker: str | None
    reason: str


@dataclass(frozen=True)
class ParseResult:
    """A preset parser's full output: the BUY/SELL rows it successfully
    extracted; `rows_skipped`, how many rows in the file were read but
    never a BUY/SELL attempt at all (dividends, interest, deposits,
    corporate actions, ...) — exists purely so the import preview can tell
    the user "N rows were ignored" without the caller re-reading the file
    itself; and `invalid_rows`, every BUY/SELL attempt that couldn't be
    parsed (see `InvalidRow`) — always reported, never silently dropped,
    so the user can see exactly which rows didn't make it in and why."""

    rows: list[ParsedRow]
    rows_skipped: int
    invalid_rows: list[InvalidRow]


_TRADING212_REQUIRED_COLUMNS = (
    "Action",
    "Time (UTC)",
    "Ticker",
    "No. of shares",
    "Price / share",
    "Currency (Price / share)",
    "Exchange rate",
    "ID",
)

_GENERIC_REQUIRED_COLUMNS = ("date", "ticker", "type", "no_of_shares", "price_native")


def _dict_reader(file: IO[Any]) -> csv.DictReader:
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    return csv.DictReader(io.StringIO(content))


def _check_columns(fieldnames: Iterable[str] | None, required: Iterable[str], preset: str) -> None:
    present = set(fieldnames or [])
    missing = [column for column in required if column not in present]
    if missing:
        raise ImportParseError(
            f"'{preset}' import is missing required column(s): {', '.join(missing)}."
        )


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _parse_positive_float(value: str | None, field_name: str, row_number: int) -> float:
    try:
        parsed = float(value) if value is not None else None
    except ValueError:
        parsed = None
    if parsed is None:
        raise ImportParseError(f"Row {row_number}: invalid {field_name} {value!r}.")
    if parsed <= 0:
        raise ImportParseError(f"Row {row_number}: {field_name} must be positive, got {value!r}.")
    return parsed


def _parse_optional_float(value: str | None) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _invert_rate(rate: float | None) -> float | None:
    """Trading 212's `Exchange rate` column is quoted default->native
    (e.g. "£1 = $1.34") — see module docstring. equicast's own `fx_rate`
    is native->default, so this inverts it to that convention before it
    ever reaches a `ParsedRow`. `None`/`0` pass through as `None` (an
    unpublished/degenerate rate is still "unresolved", not a
    ZeroDivisionError)."""
    if not rate:
        return None
    return 1 / rate


def parse_trading212_csv(file: IO[Any]) -> ParseResult:
    """Parse a Trading 212 "History" export (in the Trading 212 app:
    Settings > History > Export, Include data: Orders + Transactions) into
    a `ParseResult`. Trading 212's column set isn't officially documented,
    so this checks only the subset of headers this parser actually relies
    on and raises `ImportParseError` naming what's missing rather than
    guessing at a renamed/reordered export. `Stamp duty reserve tax` /
    `Currency conversion fee` (and their `Currency (...)` counterparts) are
    present in a real export but read as part of each row's raw data only —
    nothing in equicast's transaction shape models a trading fee/tax
    separately from the traded price, so they're never used.

    `Action` is matched case-insensitively by substring: containing "buy"
    -> BUY, "sell" -> SELL, anything else (Dividend, Interest, Deposit,
    Withdrawal, Currency conversion, a corporate action like Stock split/
    Spin off/Stock acquisition/Stock dividends, ...) is dropped and counted
    in `ParseResult.rows_skipped` — only BUY/SELL orders are ever yielded as
    a `ParsedRow`. A row matched as BUY/SELL whose data can't be parsed
    (see `_build_trading212_row`) is collected into `ParseResult.invalid_rows`
    instead — see module docstring for why this never aborts the rest of
    the file."""
    reader = _dict_reader(file)
    _check_columns(reader.fieldnames, _TRADING212_REQUIRED_COLUMNS, "trading212")

    rows: list[ParsedRow] = []
    skipped = 0
    invalid: list[InvalidRow] = []
    for row_number, row in enumerate(reader, start=2):  # header is row 1
        action = (row.get("Action") or "").strip().lower()
        if "buy" in action:
            row_type = "BUY"
        elif "sell" in action:
            row_type = "SELL"
        else:
            skipped += 1
            continue

        ticker = _clean(row.get("Ticker"))
        try:
            rows.append(_build_trading212_row(row_number, row, row_type, ticker))
        except ImportParseError as exc:
            invalid.append(InvalidRow(row_number=row_number, ticker=ticker, reason=str(exc)))
    return ParseResult(rows=rows, rows_skipped=skipped, invalid_rows=invalid)


def _build_trading212_row(
    row_number: int, row: dict[str, str], row_type: str, ticker: str | None
) -> ParsedRow:
    """Build one `ParsedRow` from a Trading 212 row already matched as
    BUY/SELL, raising `ImportParseError` (caught by the caller, see
    `parse_trading212_csv`) for anything that can't be turned into a usable
    trade — a missing `Time (UTC)`/`Ticker`, or a non-positive
    `No. of shares`/`Price / share` (the fractional-share-cashed-out-after-
    a-corporate-action case a real export can carry — see module
    docstring)."""
    time_value = _clean(row.get("Time (UTC)"))
    if time_value is None:
        raise ImportParseError(f"Row {row_number}: missing Time (UTC).")
    date = time_value.split(" ")[0].split("T")[0]

    if ticker is None:
        raise ImportParseError(f"Row {row_number}: missing Ticker.")

    return ParsedRow(
        external_id=_clean(row.get("ID")),
        date=date,
        type=row_type,
        ticker=ticker,
        asset_class=None,
        isin=_clean(row.get("ISIN")),
        name=_clean(row.get("Name")),
        no_of_shares=_parse_positive_float(row.get("No. of shares"), "No. of shares", row_number),
        price_native=_parse_positive_float(row.get("Price / share"), "Price / share", row_number),
        currency=_clean(row.get("Currency (Price / share)")),
        fx_rate=_invert_rate(_parse_optional_float(row.get("Exchange rate"))),
        raw=dict(row),
    )


def parse_generic_csv(file: IO[Any]) -> ParseResult:
    """Parse equicast's own minimal generic-CSV schema —
    `date, ticker, type, no_of_shares, price_native` required;
    `asset_class, currency, fx_rate, external_id` optional. Every row is
    treated as a BUY/SELL attempt (there's no broker-specific set of
    "other" transaction kinds to expect in a file the user built by hand,
    unlike the Trading 212 preset) — `rows_skipped` is always 0 for this
    preset; a row with an invalid `type` (not "BUY"/"SELL") or otherwise
    unusable data (see `_build_generic_row`) is collected into
    `ParseResult.invalid_rows` instead of aborting the rest of the file."""
    reader = _dict_reader(file)
    _check_columns(reader.fieldnames, _GENERIC_REQUIRED_COLUMNS, "generic")

    rows: list[ParsedRow] = []
    invalid: list[InvalidRow] = []
    for row_number, row in enumerate(reader, start=2):
        ticker = _clean(row.get("ticker"))
        try:
            rows.append(_build_generic_row(row_number, row, ticker))
        except ImportParseError as exc:
            invalid.append(InvalidRow(row_number=row_number, ticker=ticker, reason=str(exc)))
    return ParseResult(rows=rows, rows_skipped=0, invalid_rows=invalid)


def _build_generic_row(row_number: int, row: dict[str, str], ticker: str | None) -> ParsedRow:
    """Build one `ParsedRow` from a generic-CSV row, raising
    `ImportParseError` (caught by the caller, see `parse_generic_csv`) for
    anything that can't be turned into a usable trade — a missing
    `date`/`ticker`, an invalid `type`, or a non-positive
    `no_of_shares`/`price_native`."""
    date = _clean(row.get("date"))
    if date is None:
        raise ImportParseError(f"Row {row_number}: missing date.")

    if ticker is None:
        raise ImportParseError(f"Row {row_number}: missing ticker.")

    row_type = (row.get("type") or "").strip().upper()
    if row_type not in ("BUY", "SELL"):
        raise ImportParseError(
            f"Row {row_number}: type must be BUY or SELL, got {row.get('type')!r}."
        )

    return ParsedRow(
        external_id=_clean(row.get("external_id")),
        date=date,
        type=row_type,
        ticker=ticker,
        asset_class=_clean(row.get("asset_class")),
        isin=None,
        name=None,
        no_of_shares=_parse_positive_float(row.get("no_of_shares"), "no_of_shares", row_number),
        price_native=_parse_positive_float(row.get("price_native"), "price_native", row_number),
        currency=_clean(row.get("currency")),
        fx_rate=_parse_optional_float(row.get("fx_rate")),
        raw=dict(row),
    )


#: Registry of import presets — `backend/transactions/import_views.py`
#: looks up the caller-supplied preset name here rather than importing
#: parser functions by name, so adding a new broker preset never touches
#: the view layer's control flow, only this dict.
PRESETS: dict[str, Callable[[IO[Any]], ParseResult]] = {
    "generic": parse_generic_csv,
    "trading212": parse_trading212_csv,
}
