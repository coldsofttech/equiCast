"""Class-based client for corporate events (earnings, analyst rating
changes, stock splits) on any yfinance equity-like symbol."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from equicast_datafeed import DatafeedClient, round_value, warn_once

logger = logging.getLogger(__name__)

#: Shown once per process on the first EventsClient construction. Distinct
#: from equicast-datafeed's own YFINANCE_DATA_DISCLAIMER (rather than
#: reusing it) so it's always visible on its own, the same way
#: equicast-dividends' and equicast-metrics' disclaimers are - not deduped
#: away just because DatafeedClient/StockClient already logged theirs
#: earlier in the same process.
EQUICAST_EVENTS_DISCLAIMER = (
    "equicast-events: earnings, analyst rating, and stock split data via yfinance "
    "(Yahoo Finance), for educational purposes only - not financial advice."
)

#: Rows fetched from yfinance's earnings-dates call by default - enough to
#: cover this year's reported quarters plus the next few estimated ones.
EARNINGS_DEFAULT_LIMIT = 12

#: `events(full_load=True)` earnings-dates row limit - yfinance's own hard
#: cap (it raises above this), not a guarantee of full history.
EARNINGS_FULL_LOAD_LIMIT = 100


def _to_float(value: Any) -> float | None:
    """`value` as a float, or `None` for missing/NaN - pandas represents an
    unreported EPS Estimate/Reported EPS/Surprise(%) cell as NaN, which
    `round_value`'s `is not None` check alone wouldn't catch."""
    if value is None or pd.isna(value):
        return None
    return float(value)


class EventsClient:
    """Fetches corporate events for any yfinance equity-like symbol - a
    stock ticker (`AAPL`) today, an ETF ticker in the future - mirroring
    `equicast-dividends`' `DividendsClient` and `equicast-metrics`'
    `MetricsClient`: a small, generic client built on `equicast-datafeed`,
    reusable by any asset-class package.

    `events()` returns one combined list covering three distinct kinds of
    event - earnings reports, analyst rating changes, and stock splits -
    each record tagged by `event_type` with only that type's fields
    populated (the rest `None`), rather than three separate methods, so a
    single `events.parquet` per year can hold everything that happened to a
    ticker in one place.
    """

    def __init__(self, symbol: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, EQUICAST_EVENTS_DISCLAIMER)
        self.symbol = symbol.upper()
        self._datafeed = datafeed or DatafeedClient()

    def events(self, full_load: bool = False) -> list[dict[str, Any]]:
        """Return one record per event: {ticker, event_type, date,
        eps_estimate, reported_eps, surprise_pct, firm, from_grade,
        to_grade, action, ratio, last_updated, source}.

        By default covers this calendar year to date plus any future-dated
        entries (`date >= this year`, not `== this year`) - only earnings
        ever has any (estimated future report dates); rating changes and
        splits are purely historical, so this is a no-op for them - same
        year-filter-after-fetch convention as `DividendsClient.dividends()`.
        With `full_load=True`, covers this symbol's entire available
        history instead, future entries included either way (earnings
        dates still capped at yfinance's own 100-row limit; rating changes
        and splits have no such cap, so those are always complete either
        way).

        `surprise_pct`/`ratio` are passed through as yfinance reports them
        (percentage points and a raw ratio respectively, not normalized to
        a 0-1 fraction the way e.g. `dividend_yield` is elsewhere).
        """
        fetched_at = datetime.now(UTC).isoformat()
        records = [
            *self._earnings_records(full_load, fetched_at),
            *self._rating_records(fetched_at),
            *self._split_records(fetched_at),
        ]

        if not full_load:
            current_year = datetime.now(UTC).year
            records = [record for record in records if int(record["date"][:4]) >= current_year]

        return records

    def _record(self, event_type: str, date: str, fetched_at: str, **fields: Any) -> dict[str, Any]:
        return {
            "ticker": self.symbol,
            "event_type": event_type,
            "date": date,
            "eps_estimate": None,
            "reported_eps": None,
            "surprise_pct": None,
            "firm": None,
            "from_grade": None,
            "to_grade": None,
            "action": None,
            "ratio": None,
            "last_updated": fetched_at,
            "source": "yfinance",
            **fields,
        }

    def _earnings_records(self, full_load: bool, fetched_at: str) -> list[dict[str, Any]]:
        limit = EARNINGS_FULL_LOAD_LIMIT if full_load else EARNINGS_DEFAULT_LIMIT
        earnings = self._datafeed.get_earnings_dates(self.symbol, limit=limit)
        if earnings is None or earnings.empty:
            return []

        return [
            self._record(
                "earnings",
                date.date().isoformat(),
                fetched_at,
                eps_estimate=round_value(_to_float(row.get("EPS Estimate"))),
                reported_eps=round_value(_to_float(row.get("Reported EPS"))),
                surprise_pct=round_value(_to_float(row.get("Surprise(%)"))),
            )
            for date, row in earnings.iterrows()
        ]

    def _rating_records(self, fetched_at: str) -> list[dict[str, Any]]:
        ratings = self._datafeed.get_upgrades_downgrades(self.symbol)
        if ratings is None or ratings.empty:
            return []

        return [
            self._record(
                "rating",
                date.date().isoformat(),
                fetched_at,
                firm=row.get("Firm"),
                from_grade=row.get("FromGrade") or None,
                to_grade=row.get("ToGrade") or None,
                action=row.get("Action"),
            )
            for date, row in ratings.iterrows()
        ]

    def _split_records(self, fetched_at: str) -> list[dict[str, Any]]:
        splits = self._datafeed.get_splits(self.symbol)
        if splits is None or splits.empty:
            return []

        return [
            self._record(
                "split", date.date().isoformat(), fetched_at, ratio=round_value(float(ratio))
            )
            for date, ratio in splits.items()
        ]
