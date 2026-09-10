"""Class-based client for a single futures contract, backed by yfinance via
equicast-datafeed.

A future is a single yfinance symbol (like a stock ticker), not a pair
(like FX) — so its shape mirrors `equicast_benchmark.BenchmarkClient`
exactly (no dividends, no fundamentals; a futures contract pays none and
has no earnings/balance sheet), just keyed by a single `key`/`symbol`
instead of a `from_currency`/`to_currency` pair.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from equicast_datafeed import YFINANCE_DATA_DISCLAIMER, DatafeedClient, round_value, warn_once

logger = logging.getLogger(__name__)

#: yfinance's own trailing 52-week window, reused as the "year" window for
#: year_open/year_high/year_low/year_close — same as equicast-fx/-stock/
#: -benchmark.
YEAR_HISTORY_PERIOD = "1y"

#: Default `prices()` window: this calendar year only.
PRICES_DEFAULT_PERIOD = "ytd"

#: `prices(full_load=True)` window: everything yfinance has for this future.
PRICES_FULL_LOAD_PERIOD = "max"


def _midpoint(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return (low + high) / 2


class FutureClient:
    """Fetches profile and price data for one futures contract."""

    def __init__(self, key: str, symbol: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, YFINANCE_DATA_DISCLAIMER)
        self.key = key.upper()
        self.symbol = symbol
        self._datafeed = datafeed or DatafeedClient()

    def profile(self) -> dict[str, Any]:
        """Return profile and price-range data for this future."""
        info = self._datafeed.get_info(self.symbol)
        history = self._datafeed.get_history(self.symbol, period=YEAR_HISTORY_PERIOD)

        market_time = info.get("regularMarketTime")
        last_updated = (
            datetime.fromtimestamp(market_time, tz=UTC).isoformat()
            if market_time is not None
            else datetime.now(UTC).isoformat()
        )

        day_high = info.get("regularMarketDayHigh")
        day_low = info.get("regularMarketDayLow")
        day_close = info.get("regularMarketPrice")

        year_open = float(history["Open"].iloc[0]) if not history.empty else None
        year_high = info.get("fiftyTwoWeekHigh")
        year_low = info.get("fiftyTwoWeekLow")

        return {
            "key": self.key,
            "symbol": self.symbol,
            "name": info.get("longName") or info.get("shortName"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "region": info.get("region"),
            "last_updated": last_updated,
            "source": "yfinance",
            "day_open": round_value(info.get("regularMarketOpen")),
            "day_high": round_value(day_high),
            "day_low": round_value(day_low),
            "day_close": round_value(day_close),
            "year_open": round_value(year_open),
            "year_high": round_value(year_high),
            "year_low": round_value(year_low),
            "year_close": round_value(day_close),
        }

    def prices(self, full_load: bool = False) -> list[dict[str, Any]]:
        """Return one daily OHLC record per trading day.

        By default covers this calendar year only (year-to-date). With
        `full_load=True`, covers this future's entire yfinance history
        instead.
        """
        period = PRICES_FULL_LOAD_PERIOD if full_load else PRICES_DEFAULT_PERIOD
        currency = self._datafeed.get_info(self.symbol).get("currency")
        history = self._datafeed.get_history(self.symbol, period=period)
        fetched_at = datetime.now(UTC).isoformat()

        records = []
        for date, row in history.iterrows():
            high = float(row["High"])
            low = float(row["Low"])
            records.append(
                {
                    "key": self.key,
                    "symbol": self.symbol,
                    "currency": currency,
                    "date": date.date().isoformat(),
                    "open": round_value(float(row["Open"])),
                    "high": round_value(high),
                    "low": round_value(low),
                    "close": round_value(float(row["Close"])),
                    "average": round_value(_midpoint(low, high)),
                    "last_updated": fetched_at,
                    "source": "yfinance",
                }
            )
        return records
