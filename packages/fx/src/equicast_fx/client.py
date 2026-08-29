"""Class-based client for a single FX pair, backed by yfinance via equicast-datafeed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from equicast_datafeed import DatafeedClient

#: yfinance's own trailing 52-week window, reused as the "year" window for
#: year_open/year_high/year_low/year_close/year_average.
YEAR_HISTORY_PERIOD = "1y"

#: Default `prices()` window: this calendar year only.
PRICES_DEFAULT_PERIOD = "ytd"

#: `prices(full_load=True)` window: everything yfinance has for this pair.
PRICES_FULL_LOAD_PERIOD = "max"


def _midpoint(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return (low + high) / 2


class FXClient:
    """Fetches market data for one `from_currency` -> `to_currency` FX pair."""

    def __init__(
        self,
        from_currency: str,
        to_currency: str,
        datafeed: DatafeedClient | None = None,
    ) -> None:
        self.from_currency = from_currency.upper()
        self.to_currency = to_currency.upper()
        self._datafeed = datafeed or DatafeedClient()

    @property
    def symbol(self) -> str:
        """The yfinance ticker symbol for this pair, e.g. `GBPUSD=X`."""
        return f"{self.from_currency}{self.to_currency}=X"

    def profile(self) -> dict[str, Any]:
        """Return profile, price-range, and moving-average data for this FX pair."""
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
            "from_currency": self.from_currency,
            "to_currency": self.to_currency,
            "exchange": info.get("exchange"),
            "region": info.get("region"),
            "description": info.get("longName") or info.get("shortName"),
            "last_updated": last_updated,
            "source": "yfinance",
            "day_open": info.get("regularMarketOpen"),
            "day_high": day_high,
            "day_low": day_low,
            "day_close": day_close,
            "day_average": _midpoint(day_low, day_high),
            "year_open": year_open,
            "year_high": year_high,
            "year_low": year_low,
            "year_close": day_close,
            "year_average": _midpoint(year_low, year_high),
            "moving_average_50_days": info.get("fiftyDayAverage"),
            "moving_average_200_days": info.get("twoHundredDayAverage"),
        }

    def prices(self, full_load: bool = False) -> list[dict[str, Any]]:
        """Return one daily OHLC record per trading day.

        By default covers this calendar year only (year-to-date). With
        `full_load=True`, covers this pair's entire yfinance history instead.
        """
        period = PRICES_FULL_LOAD_PERIOD if full_load else PRICES_DEFAULT_PERIOD
        history = self._datafeed.get_history(self.symbol, period=period)
        fetched_at = datetime.now(UTC).isoformat()

        records = []
        for date, row in history.iterrows():
            high = float(row["High"])
            low = float(row["Low"])
            records.append(
                {
                    "from_currency": self.from_currency,
                    "to_currency": self.to_currency,
                    "date": date.date().isoformat(),
                    "open": float(row["Open"]),
                    "high": high,
                    "low": low,
                    "close": float(row["Close"]),
                    "average": _midpoint(low, high),
                    "last_updated": fetched_at,
                    "source": "yfinance",
                }
            )
        return records
