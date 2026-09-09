"""Class-based client for reading equicast's S3 market-data layout.

Generic across consumers (Django backend, Lambda, scripts) and across asset
classes (`fx`/`stock`/`etf`/`benchmark`) — it only knows the S3 key layout
the ingestion pipelines write to (`<asset_class>=<symbol>/profile.parquet`,
`<asset_class>=<symbol>/price/current.parquet` and
`<asset_class>=<symbol>/price/history.parquet`,
`<asset_class>=<symbol>/dividend/{history,current,future}.parquet`,
`<asset_class>=<symbol>/forecasting/dividends.parquet`,
`catalog/<asset_class>.parquet` — see `equicast_core.catalog` for how the
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

#: Every asset class this client (and the backend views built on it) will
#: accept for a direct, explicit request — a symbol's own profile/metrics/
#: prices/dividends, or a `search()` call that explicitly names it via
#: `asset_classes`. Deliberately broader than `DEFAULT_SEARCH_ASSET_CLASSES`
#: below: `benchmark` is fetchable/searchable on request (e.g. the holding
#: page's "compare against a benchmark" picker explicitly searches
#: `asset_classes=["benchmark"]`), but isn't one of the classes a plain,
#: unfiltered search (TopbarSearch, SearchPage's "All types") scans.
ASSET_CLASSES = ("fx", "stock", "etf", "benchmark")

#: Every asset class `search()` scans when no `asset_classes` filter is
#: given, in a fixed order so results are grouped predictably rather than
#: interleaved by whatever order a caller happened to pass filters in.
#: Narrower than `ASSET_CLASSES` on purpose — see that constant's docstring
#: for why `benchmark` is opt-in only, not part of this default set.
DEFAULT_SEARCH_ASSET_CLASSES = ("fx", "stock", "etf")

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

    def get_metrics(self, asset_class: str, symbol: str) -> dict[str, Any] | None:
        """Return the single metrics record for `symbol`, or `None` if this
        ticker/pair has no `metrics.parquet` in the bucket.

        Always carries the generic risk/performance fields
        (`volatility`/`sharpe_ratio`/`max_drawdown`/`cagr_1y`..`cagr_10y` —
        see `equicast_metrics.MetricsClient.metrics()`); a stock's record
        additionally carries the valuation/fundamental fields
        (`trailing_pe`, etc. — see `.fundamentals()`), merged in by each
        ingestion pipeline's own CLI before writing (etf/fx have no
        fundamentals, so their `metrics.parquet` only ever has the generic
        fields).
        """
        key = f"{asset_class.lower()}={symbol.upper()}/metrics.parquet"
        rows = self._read_parquet(key)
        if not rows:
            return None
        return rows[0]

    def get_dividends(self, asset_class: str, symbol: str) -> dict[str, Any] | None:
        """Return `{ticker, currency, last_updated, dividends}` for `symbol`,
        combining every dividend Parquet an ingestion pipeline writes into
        one chronological list, or `None` if none of them exist for this
        ticker/pair yet.

        Each entry in `dividends` is tagged by a `status`:
          - `"paid"` — an already-happened payout, from `dividend/
            history.parquet` and `dividend/current.parquet` (see
            `equicast_stock/equicast_etf`'s `write_dividend_parquet`).
            `payment_date` is always `None` here — yfinance's dividend
            history has no payment-date field (see
            `equicast_dividends.DividendsClient.dividends`'s docstring).
          - `"declared"` — a real, yfinance-confirmed upcoming payout, from
            `dividend/future.parquet` (see `DividendsClient.
            future_dividends`) — 0 or 1 row, per ticker. `payment_date` is
            whatever that row has (sometimes `None` too, when yfinance
            hasn't reported one yet).
          - `"estimated"` — a computed projection, from `forecasting/
            dividends.parquet` (see `equicast_forecasting.dividends`).
            `payment_date` is always `None` — this is a projected ex-date
            only, with no payment-date concept.

        Deliberately unfiltered by date (`"estimated"` rows in particular
        span years on both sides of today - see `equicast_forecasting.
        dividends`'s docstring) and not deduplicated where a `"declared"`
        and an `"estimated"` row estimate the same real-world payout -
        callers needing "upcoming only" or "declared wins over an
        overlapping estimate" (e.g. a holding page's upcoming-dividends
        cards) apply that themselves, the same way callers of `get_prices`
        pick their own display range rather than this client guessing one.
        """
        prefix = f"{asset_class.lower()}={symbol.upper()}"
        paid_rows = (self._read_parquet(f"{prefix}/dividend/history.parquet") or []) + (
            self._read_parquet(f"{prefix}/dividend/current.parquet") or []
        )
        declared_rows = self._read_parquet(f"{prefix}/dividend/future.parquet") or []
        estimated_rows = self._read_parquet(f"{prefix}/forecasting/dividends.parquet") or []
        if not (paid_rows or declared_rows or estimated_rows):
            return None

        dividends = [
            *(
                {
                    "ticker": row["ticker"],
                    "currency": row["currency"],
                    "ex_dividend_date": row["ex_dividend_date"],
                    "payment_date": None,
                    "price": row["price"],
                    "status": "paid",
                    "last_updated": row["last_updated"],
                    "source": row["source"],
                }
                for row in paid_rows
            ),
            *(
                {
                    "ticker": row["ticker"],
                    "currency": row["currency"],
                    "ex_dividend_date": row["ex_dividend_date"],
                    "payment_date": row.get("payment_date"),
                    "price": row["price"],
                    "status": "declared",
                    "last_updated": row["last_updated"],
                    "source": row["source"],
                }
                for row in declared_rows
            ),
            *(
                {
                    "ticker": row["ticker"],
                    "currency": row["currency"],
                    "ex_dividend_date": row["ex_dividend_date"],
                    "payment_date": None,
                    "price": row["price"],
                    "status": "estimated",
                    "last_updated": row["last_updated"],
                    "source": row["source"],
                }
                for row in estimated_rows
            ),
        ]
        dividends.sort(key=lambda record: record["ex_dividend_date"])

        return {
            "ticker": dividends[0]["ticker"],
            "currency": dividends[0]["currency"],
            "last_updated": max(record["last_updated"] for record in dividends),
            "dividends": dividends,
        }

    def get_news(self, asset_class: str, symbol: str) -> dict[str, Any] | None:
        """Return `{ticker, last_updated, news}` for `symbol`, or `None` if
        this ticker/pair has no `news.parquet` in the bucket (yfinance
        reported no articles in the trailing month - see
        `equicast_news.NewsClient` - or this ticker hasn't been ingested
        yet). `ticker` echoes the requested `symbol` (uppercased), same
        convention as `get_prices`, rather than trusting a `ticker` field on
        the rows themselves - a benchmark's news.parquet rows carry the
        underlying yfinance symbol there (e.g. "^GSPC"), not the benchmark
        key ("SP500") this method is actually called with.

        `news` is every row of news.parquet, newest first
        (`published_at` descending) - already written newest-first by
        `NewsClient.news()`, but re-sorted here defensively rather than
        trusted as an on-disk invariant. `last_updated` is the freshest
        value across every row (in practice all rows share one value, from
        a single ingestion run - see `NewsClient.news()` - but this doesn't
        assume that).
        """
        key = f"{asset_class.lower()}={symbol.upper()}/news.parquet"
        rows = self._read_parquet(key)
        if not rows:
            return None

        rows = sorted(rows, key=lambda row: row["published_at"], reverse=True)
        return {
            "ticker": symbol.upper(),
            "last_updated": max(row["last_updated"] for row in rows),
            "news": rows,
        }

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
        currency doesn't change day to day) — `None` for an asset class
        whose price rows carry no `currency` field at all (fx: a pair
        converts *between* two currencies rather than being priced *in*
        one, see `equicast_fx.writer`); `last_updated`/`source` reflect
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
            "currency": rows[0].get("currency"),
            "last_updated": freshest["last_updated"],
            "source": freshest["source"],
            "prices": prices,
        }

    def get_price_on_date(
            self, asset_class: str, symbol: str, on_date: str
    ) -> dict[str, Any] | None:
        """Return `{date, close, currency}` for the nearest published
        trading day on or before `on_date` ("YYYY-MM-DD") — weekends/
        holidays have no row, so e.g. a Saturday `on_date` resolves to that
        week's Friday close. `None` if nothing is published on or before
        `on_date` for this symbol (before this ticker's earliest published
        history, or no data at all).

        Unlike `get_prices`, always reads both `price/current.parquet` and
        `price/history.parquet` regardless of `on_date` — a single-date
        lookup near a year boundary can't cheaply rule out needing the
        other file the way a whole-range cutoff can (see `get_prices`'s
        `needs_history`). `currency` is `None` for fx (a pair converts
        *between* two currencies rather than being priced *in* one — see
        `get_prices`).
        """
        prefix = f"{asset_class.lower()}={symbol.upper()}/price"
        rows: list[dict[str, Any]] = []
        history_rows = self._read_parquet(f"{prefix}/history.parquet")
        if history_rows:
            rows.extend(history_rows)
        current_rows = self._read_parquet(f"{prefix}/current.parquet")
        if current_rows:
            rows.extend(current_rows)

        eligible = [r for r in rows if r["date"] <= on_date]
        if not eligible:
            return None
        latest = max(eligible, key=lambda r: r["date"])
        return {
            "date": latest["date"], "close": latest["close"], "currency": latest.get("currency")
        }

    def get_fx_rate_on_date(
        self, from_currency: str, to_currency: str, on_date: str
    ) -> float | None:
        """Convert 1 unit of `from_currency` into `to_currency` as of the
        nearest published trading day on or before `on_date` — `1.0` with
        no lookup at all when the two currencies are the same. Tries the
        direct pair (`<from><to>`, e.g. "USDGBP" quotes GBP per 1 USD — see
        `equicast_fx.client`) first, then the inverted pair (taking its
        reciprocal) if that's what's published instead — same fallback the
        frontend's `resolveFxRate` (holdingFinancials.js) uses for the
        current-only rate, just at a historical date here. `None` if
        neither pair has anything published on or before `on_date`."""
        if from_currency == to_currency:
            return 1.0
        direct = self.get_price_on_date("fx", f"{from_currency}{to_currency}", on_date)
        if direct is not None and direct["close"]:
            return direct["close"]
        inverted = self.get_price_on_date("fx", f"{to_currency}{from_currency}", on_date)
        if inverted is not None and inverted["close"]:
            return 1 / inverted["close"]
        return None

    def get_catalog(self, asset_class: str) -> list[dict[str, Any]]:
        """Return every `{ticker, name, type, current_price, currency,
        website, market_cap, exchange, region, sector, industry}` row this
        asset class's ingestion pipeline last published (see
        `equicast_core.catalog`), or `[]` if no catalog has been uploaded
        yet for it."""
        rows = self._read_parquet(catalog_key(asset_class))
        return rows if rows is not None else []

    def _latest_fx_rate(
        self, from_currency: str, to_currency: str, fx_catalog: dict[str, dict[str, Any]]
    ) -> float | None:
        """Convert 1 unit of `from_currency` into `to_currency` using the fx
        catalog's own last-published `current_price` — the direct pair
        (`<from><to>`) if published, else the reciprocal of the inverted
        pair (`<to><from>`) if that's what's published instead, same
        fallback `get_fx_rate_on_date` uses, just off the catalog's latest
        snapshot rather than a specific date's price history. `1.0` with no
        lookup at all when the two currencies are the same. `None` if
        neither pair is in `fx_catalog`."""
        if from_currency == to_currency:
            return 1.0
        direct = fx_catalog.get(f"{from_currency}{to_currency}")
        if direct is not None and direct.get("current_price") is not None:
            return direct["current_price"]
        inverted = fx_catalog.get(f"{to_currency}{from_currency}")
        if inverted is not None and inverted.get("current_price"):
            return 1 / inverted["current_price"]
        return None

    def enrich_holdings(
        self, holdings: list[dict[str, Any]], default_currency: str
    ) -> list[dict[str, Any]]:
        """Return `holdings` with market-derived display/valuation fields
        merged in from each ticker's catalog row (`catalog/<asset_class>.
        parquet` — see `equicast_core.catalog`): `name`/`sector`/`industry`/
        `website` (`website` backs the frontend's favicon-based AssetIcon),
        `market_cap` (a stock's real market cap, an etf's total assets as
        the closest comparable "size" figure a fund has — same convention
        as `search`'s `min_market_cap`/`max_market_cap` filters), and
        `current_price_native`/`current_price` (the catalog's own
        last-published price, FX-converted to `default_currency` — the same
        convention `average_price`/`invested`/`dividends` already use, see
        `transactions.views.resolve_converted_amounts`) and `last_updated`
        (the catalog's own, i.e. that ticker's ingestion pipeline's last run
        — see `equicast_core.catalog.build_catalog_rows`), so a caller can
        derive current value/profit-loss, or a "Synced" date, without a
        market-data round trip per ticker.

        Reads each distinct asset class present in `holdings` once (via
        `get_catalog`), plus the `fx` catalog for currency conversion, so a
        user with many holdings across a handful of asset classes costs a
        handful of S3 reads total, not one profile fetch per holding. The FX
        rate used is the `fx` catalog's own latest published rate (see
        `_latest_fx_rate`), not a rate as of a specific date, so this always
        reflects whatever the fx ingestion pipeline last ran without a
        second, date-scoped S3 read per currency pair. A field is `None`
        whenever it can't be resolved (unpublished ticker, no fx rate
        published for the pair) rather than raising — same degrade-
        gracefully behavior as `resolve_converted_amounts`.
        """
        if not holdings:
            return holdings

        catalogs: dict[str, dict[str, dict[str, Any]]] = {}
        for holding in holdings:
            asset_class = holding["asset_class"]
            if asset_class not in catalogs:
                catalogs[asset_class] = {
                    row["ticker"]: row for row in self.get_catalog(asset_class)
                }
        fx_catalog = catalogs.get("fx") or {
            row["ticker"]: row for row in self.get_catalog("fx")
        }

        rates: dict[str, float | None] = {}
        enriched = []
        for holding in holdings:
            row = catalogs[holding["asset_class"]].get(holding["ticker"])
            native_currency = row.get("currency") if row else None
            current_price_native = row.get("current_price") if row else None
            if native_currency and native_currency not in rates:
                rates[native_currency] = self._latest_fx_rate(
                    native_currency, default_currency, fx_catalog
                )
            rate = rates.get(native_currency) if native_currency else None
            current_price = (
                current_price_native * rate
                if current_price_native is not None and rate is not None
                else None
            )
            enriched.append(
                {
                    **holding,
                    "name": row.get("name") if row else None,
                    "sector": row.get("sector") if row else None,
                    "industry": row.get("industry") if row else None,
                    "website": row.get("website") if row else None,
                    "market_cap": row.get("market_cap") if row else None,
                    "current_price_native": current_price_native,
                    "current_price": current_price,
                    "last_updated": row.get("last_updated") if row else None,
                }
            )
        return enriched

    def search(
        self,
        query: str,
        asset_classes: list[str] | None = None,
        min_market_cap: float | None = None,
        max_market_cap: float | None = None,
        exchange: str | None = None,
        region: str | None = None,
        sector: str | None = None,
        industry: str | None = None,
    ) -> list[dict[str, Any]]:
        """Case-insensitive substring match of `query` against every
        catalog row's `ticker` and `name`, across `asset_classes` (default:
        `DEFAULT_SEARCH_ASSET_CLASSES` — `benchmark` is scanned only when a
        caller explicitly asks for it, e.g. `asset_classes=["benchmark"]`;
        see that constant's docstring for why). Reads each scanned asset
        class's catalog file once (via `get_catalog`) rather than the
        bucket itself — no per-ticker S3 reads here, unlike
        `get_profile`/`get_prices`.

        `min_market_cap`/`max_market_cap`, `exchange`, `region`, `sector`,
        and `industry`, when given, additionally filter stock/etf rows by
        their `market_cap` (a stock's real market cap, an etf's total
        assets as the closest comparable "size" figure a fund has),
        `equicast_core.catalog.build_catalog_rows`). fx rows have none of
        those concepts for a currency pair (always `None`), same as a
        benchmark row for `market_cap`/`sector`/`industry` — any row
        missing the field being filtered on is excluded whenever that
        filter is given, rather than guessed to match, there's nothing to
        compare it against. An etf row's `sector`/`industry` are instead
        always the fixed "Exchange Traded Fund" (see
        `equicast_etf.client.ETFClient.profile`), so it matches only that
        value under either filter rather than always being excluded.
        `exchange`/`region`/`sector`/`industry` match case-insensitively
        against the row's exact value (not a substring, unlike `query`),
        since all four are short codes/labels (e.g. "NMS"/"us"/
        "Technology"), not free text.

        Results are sorted by ticker for a stable order across calls (the
        caller — e.g. the Django view — owns pagination on top of this)."""
        classes = asset_classes if asset_classes is not None else DEFAULT_SEARCH_ASSET_CLASSES
        query_lower = query.lower()
        filter_by_market_cap = min_market_cap is not None or max_market_cap is not None
        exchange_lower = exchange.lower() if exchange is not None else None
        region_lower = region.lower() if region is not None else None
        sector_lower = sector.lower() if sector is not None else None
        industry_lower = industry.lower() if industry is not None else None

        matches = []
        for asset_class in classes:
            for row in self.get_catalog(asset_class):
                ticker = row.get("ticker") or ""
                name = row.get("name") or ""
                if query_lower not in ticker.lower() and query_lower not in name.lower():
                    continue
                if filter_by_market_cap:
                    market_cap = row.get("market_cap")
                    if market_cap is None:
                        continue
                    if min_market_cap is not None and market_cap < min_market_cap:
                        continue
                    if max_market_cap is not None and market_cap > max_market_cap:
                        continue
                if exchange_lower is not None:
                    row_exchange = row.get("exchange")
                    if row_exchange is None or row_exchange.lower() != exchange_lower:
                        continue
                if region_lower is not None:
                    row_region = row.get("region")
                    if row_region is None or row_region.lower() != region_lower:
                        continue
                if sector_lower is not None:
                    row_sector = row.get("sector")
                    if row_sector is None or row_sector.lower() != sector_lower:
                        continue
                if industry_lower is not None:
                    row_industry = row.get("industry")
                    if row_industry is None or row_industry.lower() != industry_lower:
                        continue
                matches.append(row)
        matches.sort(key=lambda row: row["ticker"])
        return matches
