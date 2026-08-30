"""Class-based client for dividend history on any yfinance equity-like symbol."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from equicast_datafeed import DatafeedClient, round_value, warn_once

logger = logging.getLogger(__name__)

#: Shown once per process on the first DividendsClient construction. Distinct
#: from equicast-datafeed's own YFINANCE_DATA_DISCLAIMER (rather than reusing
#: it) so it's always visible on its own, the same way equicast-metrics'
#: disclaimer is - not deduped away just because DatafeedClient/StockClient
#: already logged theirs earlier in the same process.
EQUICAST_DIVIDENDS_DISCLAIMER = (
    "equicast-dividends: dividend data via yfinance (Yahoo Finance), for educational "
    "purposes only - not financial advice."
)


class DividendsClient:
    """Fetches dividend history for any yfinance equity-like symbol - a stock
    ticker (`AAPL`) today, an ETF ticker in the future - since the underlying
    data (ex-dividend date, cash amount per share) is shaped the same way
    regardless of asset class, same as `equicast-metrics`' `MetricsClient` is
    generic across FX pairs and stock tickers.
    """

    def __init__(self, symbol: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, EQUICAST_DIVIDENDS_DISCLAIMER)
        self.symbol = symbol.upper()
        self._datafeed = datafeed or DatafeedClient()

    def dividends(self, full_load: bool = False) -> list[dict[str, Any]]:
        """Return one record per ex-dividend date: {ticker, currency,
        ex_dividend_date, price, last_updated, source}.

        By default covers this calendar year to date plus any future-dated
        entries (`index.year >= this year`, not `== this year`), even
        though yfinance's dividend data has no period parameter like
        `history()` does (the full series is fetched in one call
        regardless; this filters the already-fetched result by year). In
        practice this is a no-op today - yfinance's dividend history is
        derived from price-history data, which never has a date past
        today, so there's nothing to include beyond this year - but keeps
        the filter honest (year-to-date-and-beyond, not merely
        "this calendar year") should that ever change, and matches
        `EventsClient.events()`'s same convention. With `full_load=True`,
        covers this symbol's entire dividend history instead.

        yfinance's dividend history only has ex-dividend date and cash
        amount - no payment date - so there's no `payment_date` field here.
        """
        currency = self._datafeed.get_info(self.symbol).get("currency")
        dividends = self._datafeed.get_dividends(self.symbol)
        fetched_at = datetime.now(UTC).isoformat()

        if not full_load and not dividends.empty:
            current_year = datetime.now(UTC).year
            dividends = dividends[dividends.index.year >= current_year]

        records = []
        for ex_dividend_date, amount in dividends.items():
            records.append(
                {
                    "ticker": self.symbol,
                    "currency": currency,
                    "ex_dividend_date": ex_dividend_date.date().isoformat(),
                    "price": round_value(float(amount)),
                    "last_updated": fetched_at,
                    "source": "yfinance",
                }
            )
        return records
