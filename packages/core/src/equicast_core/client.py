"""Class-based client for reading equicast's S3 market-data layout.

Generic across consumers (Django backend, Lambda, scripts) and across asset
classes (`fx`/`stock`/`etf`) — it only knows the S3 key layout the ingestion
pipelines write to (`<asset_class>=<symbol>/profile.parquet`,
`<asset_class>=<symbol>/price/current.parquet` and
`<asset_class>=<symbol>/price/history.parquet`,
`catalog/<asset_class>.json` — see `equicast_core.catalog` for how the
latter is built/uploaded by each ingestion pipeline), nothing about Django
or any particular caller.
"""

from __future__ import annotations

import calendar
import json
from datetime import UTC, date, datetime
from typing import Any

import boto3
import pyarrow.parquet as pq
from pyarrow import BufferReader

from equicast_core.catalog import catalog_key

#: Every asset class `search()` scans when no `asset_classes` filter is
#: given, in a fixed order so results are grouped predictably rather than
#: interleaved by whatever order a caller happened to pass filters in.
ASSET_CLASSES = ("fx", "stock", "etf")

#: Every price range get_prices()/PricesView accepts, in the order a range
#: picker should offer them. "max" is also the default when none is given
#: — the same "whatever's published" behaviour get_prices had before range
#: support existed (it only ever read the current year), just explicit now.
PRICE_RANGES = ("1d", "5d", "1m", "6m", "ytd", "1y", "2y", "3y", "5y", "10y", "max")
DEFAULT_PRICE_RANGE = "max"

#: Calendar-month width of each range with a fixed month-based cutoff —
#: 1d/5d trim by trailing row count instead, ytd cuts at Jan 1, and max has
#: no cutoff at all (see get_prices).
_PRICE_RANGE_MONTHS = {"1m": 1, "6m": 6, "1y": 12, "2y": 24, "3y": 36, "5y": 60, "10y": 120}

#: Aggregation bucket per range. Daily source rows are returned as-is for
#: 6 months or less; 1y/2y roll up into one weekly bar per ISO week (its
#: date/close land on that week's last trading day — Friday for a normal
#: 5-day trading week); 3y and up roll up into one monthly bar per calendar
#: month (its date/close land on that month's last trading day). This keeps
#: a multi-year/max response a few hundred rows instead of several thousand
#: — this Django app runs as a Lambda behind API Gateway (see
#: backend/README.md), and Lambda caps a synchronous response at 6MB, well
#: before "several thousand daily rows" would ever get close, but a chart
#: is also unreadable at daily resolution over a decade anyway.
_PRICE_RANGE_GRANULARITY = {
    "1d": "day",
    "5d": "day",
    "1m": "day",
    "6m": "day",
    "ytd": "day",
    "1y": "week",
    "2y": "week",
    "3y": "month",
    "5y": "month",
    "10y": "month",
    "max": "month",
}


def _start_date_for_range(price_range: str, today: date) -> date | None:
    """The earliest date to include for `price_range`, or `None` when it
    has no fixed-month cutoff — 1d/5d trim by trailing row count and max
    has no cutoff at all (both handled separately in get_prices); ytd is
    also handled separately, as a plain Jan 1 cut rather than a month
    count."""
    months = _PRICE_RANGE_MONTHS.get(price_range)
    if months is None:
        return None
    month_index = today.month - 1 - months
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _aggregate_prices(rows: list[dict[str, Any]], bucket: str) -> list[dict[str, Any]]:
    """Rolls up ascending-by-date `{date, open, high, low, close}` rows into
    one OHLC row per ISO week or calendar month (`bucket` = "week"/
    "month"), or returns `rows` unchanged for `bucket == "day"`. Each
    bucket's `date` is its last (most recent) trading day; `open`/`close`
    are its first/last row's own open/close; `high`/`low` are the max/min
    across every row in the bucket."""
    if bucket == "day" or not rows:
        return rows

    buckets: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        row_date = date.fromisoformat(row["date"])
        key = row_date.isocalendar()[:2] if bucket == "week" else (row_date.year, row_date.month)
        buckets.setdefault(key, []).append(row)

    return [
        {
            "date": group[-1]["date"],
            "open": group[0]["open"],
            "high": max(r["high"] for r in group),
            "low": min(r["low"] for r in group),
            "close": group[-1]["close"],
        }
        for key, group in sorted(buckets.items())
    ]


class MarketDataClient:
    """Reads profile/price/catalog Parquet/JSON objects from one S3
    bucket."""

    def __init__(self, bucket: str, s3_client: Any = None, region_name: str | None = None) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)

    def _read_parquet(self, key: str) -> list[dict[str, Any]] | None:
        """Return every row of the Parquet object at `key`, or `None` if it
        doesn't exist. Any other S3 error propagates as-is."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=key)
        except self._s3.exceptions.NoSuchKey:
            return None
        body = response["Body"].read()
        table = pq.read_table(BufferReader(body))
        return table.to_pylist()

    def get_profile(self, asset_class: str, symbol: str) -> dict[str, Any] | None:
        """Return the single profile record for `symbol`, or `None` if this
        ticker/pair has no `profile.parquet` in the bucket.

        A stock profile's `ceos` is written as a JSON-encoded string column
        (see `equicast_stock.writer.write_profile_parquet`'s docstring —
        Parquet viewers render a native list<struct> column as
        "[object Object]", so the writer stores JSON text instead and
        documents that consumers decode it back); decoded here so every
        caller of this client gets a real list, not a raw JSON string. Only
        touched when present and still a string — etf/fx profiles have no
        `ceos` field at all, and a value that's already a list (e.g. from a
        test fixture) is left as-is rather than re-decoded.
        """
        key = f"{asset_class.lower()}={symbol.upper()}/profile.parquet"
        rows = self._read_parquet(key)
        if not rows:
            return None
        profile = rows[0]
        if isinstance(profile.get("ceos"), str):
            profile = {**profile, "ceos": json.loads(profile["ceos"])}
        return profile

    def get_prices(
        self, asset_class: str, symbol: str, price_range: str = DEFAULT_PRICE_RANGE
    ) -> dict[str, Any]:
        """Return `{ticker, currency, last_updated, source, prices}` for
        `symbol`, where `prices` is ascending-by-date `{date, open, high,
        low, close}` bars trimmed to `price_range` (one of PRICE_RANGES;
        default "max" = this ticker's entire published history). Ranges past
        6 months are aggregated to weekly ("1y"/"2y") or monthly ("3y" and
        up) bars rather than returned at daily resolution — see
        `_PRICE_RANGE_GRANULARITY`.

        Always reads `price/current.parquet` (the current calendar year),
        and also reads `price/history.parquet` (every earlier year, written
        once by a `--full-load` ingestion run — see
        `equicast_stock.writer.write_price_parquet`) whenever `price_range`
        might need an earlier date: always for "max"/"1d"/"5d" (the
        trailing-day ranges read it in case the window crosses into last
        December before this year has that many trading days published
        yet), and for any other range whose month-based cutoff falls before
        this year. "ytd" never needs it, since its cutoff is always this
        year's Jan 1.

        `currency` is read off the first matched daily row (a symbol's
        currency doesn't change day to day); `last_updated`/`source` reflect
        whichever matched daily row was written most recently (same "max of
        the parts" pattern as equicast_stock.cli's combined `last_updated`)
        — `history.parquet`/`current.parquet` are written independently
        (see equicast_stock.writer), so their own `last_updated`/`source`
        can differ. Both are read before aggregation, since an aggregated
        bucket no longer carries per-row metadata.

        Returns all-`None`/empty `prices` when nothing is published for this
        symbol/range yet — the same "not configured" signal `get_prices`
        always returned, now shaped as a dict instead of a bare list.
        """
        if price_range not in PRICE_RANGES:
            raise ValueError(
                f"Unknown price range '{price_range}'. Must be one of: {PRICE_RANGES}."
            )

        today = datetime.now(UTC).date()
        cutoff: str | None

        if price_range == "ytd":
            needs_history = False
            cutoff = date(today.year, 1, 1).isoformat()
        elif price_range in ("1d", "5d"):
            # Trailing-N trading days, not a calendar cut — history.parquet
            # covers even early January, when the current year alone might
            # not have N trading days published yet.
            needs_history = True
            cutoff = None
        elif price_range == "max":
            needs_history = True
            cutoff = None
        else:
            start_date = _start_date_for_range(price_range, today)
            assert start_date is not None  # every range but max/1d/5d/ytd has a month cutoff
            needs_history = start_date.year < today.year
            cutoff = start_date.isoformat()

        prefix = f"{asset_class.lower()}={symbol.upper()}/price"
        rows: list[dict[str, Any]] = []
        if needs_history:
            history_rows = self._read_parquet(f"{prefix}/history.parquet")
            if history_rows:
                rows.extend(history_rows)
        current_rows = self._read_parquet(f"{prefix}/current.parquet")
        if current_rows:
            rows.extend(current_rows)
        rows.sort(key=lambda r: r["date"])

        if price_range == "1d":
            rows = rows[-1:]
        elif price_range == "5d":
            rows = rows[-5:]
        elif cutoff is not None:
            rows = [r for r in rows if r["date"] >= cutoff]

        if not rows:
            return {
                "ticker": symbol.upper(),
                "currency": None,
                "last_updated": None,
                "source": None,
                "prices": [],
            }

        freshest = max(rows, key=lambda r: r["last_updated"])
        daily = [
            {
                "date": r["date"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
            }
            for r in rows
        ]
        prices = _aggregate_prices(daily, _PRICE_RANGE_GRANULARITY[price_range])
        return {
            "ticker": symbol.upper(),
            "currency": rows[0]["currency"],
            "last_updated": freshest["last_updated"],
            "source": freshest["source"],
            "prices": prices,
        }

    def get_catalog(self, asset_class: str) -> list[dict[str, Any]]:
        """Return every `{ticker, name, type, current_price}` row this
        asset class's ingestion pipeline last published (see
        `equicast_core.catalog`), or `[]` if no catalog has been uploaded
        yet for it."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=catalog_key(asset_class))
        except self._s3.exceptions.NoSuchKey:
            return []
        body = json.loads(response["Body"].read())
        return body.get("tickers", [])

    def search(self, query: str, asset_classes: list[str] | None = None) -> list[dict[str, Any]]:
        """Case-insensitive substring match of `query` against every
        catalog row's `ticker` and `name`, across `asset_classes` (default:
        every asset class — see `ASSET_CLASSES`). Reads each scanned asset
        class's catalog file once (via `get_catalog`) rather than the
        bucket itself — no per-ticker S3 reads here, unlike
        `get_profile`/`get_prices`.

        Results are sorted by ticker for a stable order across calls (the
        caller — e.g. the Django view — owns pagination on top of this)."""
        classes = asset_classes if asset_classes is not None else ASSET_CLASSES
        query_lower = query.lower()

        matches = []
        for asset_class in classes:
            for row in self.get_catalog(asset_class):
                ticker = row.get("ticker") or ""
                name = row.get("name") or ""
                if query_lower in ticker.lower() or query_lower in name.lower():
                    matches.append(row)
        matches.sort(key=lambda row: row["ticker"])
        return matches
