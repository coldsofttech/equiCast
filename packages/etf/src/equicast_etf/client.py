"""Class-based client for a single ETF ticker, backed by yfinance via equicast-datafeed."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from equicast_datafeed import YFINANCE_DATA_DISCLAIMER, DatafeedClient, round_value, warn_once

logger = logging.getLogger(__name__)

#: yfinance's own trailing 52-week window, reused as the "year" window for
#: year_open/year_high/year_low/year_close/year_average — same as
#: equicast-fx/equicast-stock.
YEAR_HISTORY_PERIOD = "1y"

#: Default `prices()` window: this calendar year only.
PRICES_DEFAULT_PERIOD = "ytd"

#: `prices(full_load=True)` window: everything yfinance has for this ticker.
PRICES_FULL_LOAD_PERIOD = "max"

#: Issuer website, keyed by a lowercase substring of yfinance's `fundFamily`
#: string for that ticker. yfinance never populates `website` for ETFs
#: (confirmed empty across Vanguard/iShares/Invesco/State Street/Schwab/
#: BlackRock-issued funds), unlike for stocks, so this is a small static
#: lookup rather than a yfinance-sourced field. Substring match (not an exact
#: dict key) because `fundFamily` itself varies by ticker even for the same
#: issuer, e.g. "iShares" (AGG) vs "BlackRock Asset Management Ireland -
#: ETF" (a UCITS fund) — both map to iShares, BlackRock's ETF brand.
_FUND_FAMILY_WEBSITES: dict[str, str] = {
    "vanguard": "https://www.vanguard.com",
    "ishares": "https://www.ishares.com",
    "blackrock": "https://www.ishares.com",
    "invesco": "https://www.invesco.com",
    "state street": "https://www.ssga.com",
    "spdr": "https://www.ssga.com",
    "schwab": "https://www.schwabassetmanagement.com",
}


def _fund_family_website(fund_family: str | None) -> str | None:
    """Best-effort issuer website for `fund_family`, from `_FUND_FAMILY_WEBSITES`.

    `None` if `fund_family` is missing or doesn't match a known issuer.
    """
    if not fund_family:
        return None
    lowered = fund_family.lower()
    for key, url in _FUND_FAMILY_WEBSITES.items():
        if key in lowered:
            return url
    return None


def _midpoint(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return (low + high) / 2


def _inception_date(info: dict[str, Any]) -> str | None:
    """Best-effort fund inception date, in the same ISO 8601 datetime format
    as `last_updated`.

    `fundInceptionDate` (epoch seconds) is yfinance's own fund-inception
    field, populated for every ETF checked. Falls back to
    `firstTradeDateMilliseconds`/`firstTradeDateEpochUtc` — the first date
    yfinance itself has trading data for this ticker — only if that's
    missing, same fallback equicast-stock's `ipo_date` uses.
    """
    inception_seconds = info.get("fundInceptionDate")
    if inception_seconds is not None:
        return datetime.fromtimestamp(inception_seconds, tz=UTC).isoformat()

    millis = info.get("firstTradeDateMilliseconds")
    if millis is not None:
        return datetime.fromtimestamp(millis / 1000, tz=UTC).isoformat()

    epoch_seconds = info.get("firstTradeDateEpochUtc")
    if epoch_seconds is not None:
        return datetime.fromtimestamp(epoch_seconds, tz=UTC).isoformat()

    return None


class ETFClient:
    """Fetches profile data for one ETF ticker."""

    def __init__(self, ticker: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, YFINANCE_DATA_DISCLAIMER)
        self.ticker = ticker.upper()
        self._datafeed = datafeed or DatafeedClient()

    @property
    def symbol(self) -> str:
        """The yfinance ticker symbol, e.g. `VOO` (no suffix, unlike FX pairs)."""
        return self.ticker

    def profile(self) -> dict[str, Any]:
        """Return profile data for this ETF ticker."""
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
            "ticker": self.ticker,
            "name": info.get("longName") or info.get("shortName"),
            "quote_type": info.get("quoteType"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "description": info.get("longBusinessSummary"),
            "category": info.get("category"),
            "fund_family": info.get("fundFamily"),
            "website": _fund_family_website(info.get("fundFamily")),
            "beta": round_value(info.get("beta3Year")),
            "expense_ratio": round_value(info.get("netExpenseRatio")),
            "dividend_rate": round_value(info.get("trailingAnnualDividendRate")),
            "dividend_yield": round_value(info.get("yield")),
            "total_assets": info.get("totalAssets"),
            "nav_price": round_value(info.get("navPrice")),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "day_open": round_value(info.get("regularMarketOpen")),
            "day_high": round_value(day_high),
            "day_low": round_value(day_low),
            "day_close": round_value(day_close),
            "day_average": round_value(_midpoint(day_low, day_high)),
            "year_open": round_value(year_open),
            "year_high": round_value(year_high),
            "year_low": round_value(year_low),
            "year_close": round_value(day_close),
            "year_average": round_value(_midpoint(year_low, year_high)),
            "moving_average_50_days": round_value(info.get("fiftyDayAverage")),
            "moving_average_200_days": round_value(info.get("twoHundredDayAverage")),
            "ytd_return": round_value(info.get("ytdReturn")),
            "three_year_average_return": round_value(info.get("threeYearAverageReturn")),
            "five_year_average_return": round_value(info.get("fiveYearAverageReturn")),
            "inception_date": _inception_date(info),
            "last_updated": last_updated,
            "source": "yfinance",
        }
