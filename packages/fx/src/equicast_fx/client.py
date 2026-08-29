"""Class-based client for a single FX pair, backed by yfinance via equicast-datafeed."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from equicast_datafeed import DatafeedClient


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
        """Return exchange/region/description metadata for this FX pair."""
        info = self._datafeed.get_info(self.symbol)

        market_time = info.get("regularMarketTime")
        last_updated = (
            datetime.fromtimestamp(market_time, tz=UTC).isoformat()
            if market_time is not None
            else datetime.now(UTC).isoformat()
        )

        return {
            "from_currency": self.from_currency,
            "to_currency": self.to_currency,
            "exchange": info.get("exchange"),
            "region": info.get("region"),
            "description": info.get("longName") or info.get("shortName"),
            "last_updated": last_updated,
            "source": "yfinance",
        }
