"""Class-based client for generic risk/performance metrics on any yfinance symbol."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from equicast_datafeed import DatafeedClient, DatafeedError, round_value, warn_once

from equicast_metrics.calculations import (
    annualized_volatility,
    cagr,
    max_drawdown,
    sharpe_ratio,
    trailing_window,
)
from equicast_metrics.exceptions import UnsupportedSymbolError
from equicast_metrics.fundamentals import compute_fundamentals

logger = logging.getLogger(__name__)

#: Shown once per process on the first MetricsClient construction.
EQUICAST_METRICS_DISCLAIMER = (
    "equicast-metrics: metrics calculated by equicast, for educational purposes only "
    "- validate accuracy independently."
)

#: The only CAGR window yfinance has a direct equivalent for (fiftyTwoWeekChangePercent).
YFINANCE_CAGR_YEARS = 1

CAGR_YEARS = (1, 2, 3, 5, 10)
METRICS_WINDOW_YEARS = 1

#: yfinance's suffix for FX pair symbols (e.g. "GBPUSD=X"), reused here to
#: reject fundamentals() calls against them - see FXClient.symbol.
FX_SYMBOL_SUFFIX = "=X"


def _cagr_1y_from_info(info: dict[str, Any]) -> float | None:
    """`fiftyTwoWeekChangePercent` is, for a 1-year window, the same figure as
    CAGR (total return over exactly one year, with no compounding needed)."""
    value = info.get("fiftyTwoWeekChangePercent")
    return round_value(float(value) / 100) if value is not None else None


def _is_fx_symbol(symbol: str) -> bool:
    return symbol.endswith(FX_SYMBOL_SUFFIX)


class MetricsClient:
    """Computes volatility, Sharpe ratio, max drawdown, and CAGR for one symbol.

    Works for any yfinance symbol - an FX pair (e.g. "GBPUSD=X") or a stock
    ticker (e.g. "AAPL") - since the underlying computation only needs a
    daily close-price history, regardless of asset class.
    """

    def __init__(self, symbol: str, datafeed: DatafeedClient | None = None) -> None:
        warn_once(logger, EQUICAST_METRICS_DISCLAIMER)
        self.symbol = symbol.upper()
        self._datafeed = datafeed or DatafeedClient()

    def metrics(self) -> dict[str, Any]:
        info = self._datafeed.get_info(self.symbol)
        history = self._datafeed.get_history(self.symbol, period="max")
        close: pd.Series = (
            history["Close"] if "Close" in history.columns else pd.Series(dtype=float)
        )
        # A still-forming trading day (e.g. fetched before the session closes)
        # can show up as a NaN close, which would otherwise poison every
        # calculation below via `.iloc[-1]`.
        close = close.dropna()

        window = trailing_window(close, METRICS_WINDOW_YEARS)

        # volatility/sharpe/max_drawdown have no yfinance equivalent at all, so
        # this record always includes at least one equicast-computed value.
        # Only cagr_1y can ever come directly from yfinance (fiftyTwoWeekChangePercent).
        cagr_values: dict[str, float | None] = {}
        for years in CAGR_YEARS:
            yfinance_value = _cagr_1y_from_info(info) if years == YFINANCE_CAGR_YEARS else None
            cagr_values[f"cagr_{years}y"] = (
                yfinance_value if yfinance_value is not None else cagr(close, years)
            )

        return {
            "volatility": annualized_volatility(window),
            "sharpe_ratio": sharpe_ratio(window),
            "max_drawdown": max_drawdown(window),
            **cagr_values,
            "last_updated": datetime.now(UTC).isoformat(),
            "source": "equicast",
        }

    def fundamentals(self) -> dict[str, Any]:
        """Valuation/fundamental metrics: PE, EPS, PEG, price-to-book/sales,
        EV/EBITDA, margins, returns, leverage, and free cash flow per share.

        Stock-only - FX pairs have no earnings or balance sheet, so this
        raises `UnsupportedSymbolError` for a symbol ending in "=X"
        (yfinance's FX pair suffix, see `FXClient.symbol`).
        """
        if _is_fx_symbol(self.symbol):
            raise UnsupportedSymbolError(
                f"fundamentals() only supports stock tickers, not FX pairs (got '{self.symbol}')"
            )

        info = self._datafeed.get_info(self.symbol)

        # compute_fundamentals() only calls these if - and at most once each
        # even if - a fallback tier actually needs the statement.
        def get_financials() -> pd.DataFrame | None:
            try:
                return self._datafeed.get_financials(self.symbol)
            except DatafeedError:
                logger.warning("Failed to fetch financials for %s", self.symbol)
                return None

        def get_balance_sheet() -> pd.DataFrame | None:
            try:
                return self._datafeed.get_balance_sheet(self.symbol)
            except DatafeedError:
                logger.warning("Failed to fetch balance sheet for %s", self.symbol)
                return None

        values, used_fallback = compute_fundamentals(info, get_financials, get_balance_sheet)

        return {
            **{key: round_value(value) for key, value in values.items()},
            "last_updated": datetime.now(UTC).isoformat(),
            "source": "equicast" if used_fallback else "yfinance",
        }
