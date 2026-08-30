"""Resilient client around yfinance: rate limiting plus retry-with-backoff."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from equicast_datafeed.disclaimers import YFINANCE_DATA_DISCLAIMER, warn_once
from equicast_datafeed.exceptions import DatafeedError
from equicast_datafeed.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


class DatafeedClient:
    """Fetches ticker info and history from yfinance with limits and retries."""

    def __init__(
        self,
        max_calls: int = 1,
        period_seconds: float = 1.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
    ) -> None:
        warn_once(logger, YFINANCE_DATA_DISCLAIMER)
        self._rate_limiter = RateLimiter(max_calls=max_calls, period_seconds=period_seconds)
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def get_info(self, symbol: str) -> dict[str, Any]:
        """Return the `.info` dict yfinance reports for `symbol`."""
        return self._call(lambda: yf.Ticker(symbol).info, symbol)

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """Return historical OHLCV data for `symbol`."""
        return self._call(
            lambda: yf.Ticker(symbol).history(period=period, interval=interval), symbol
        )

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """Return `symbol`'s annual balance sheet, most-recent period in the first column."""
        return self._call(lambda: yf.Ticker(symbol).balance_sheet, symbol)

    def get_financials(self, symbol: str) -> pd.DataFrame:
        """Return `symbol`'s annual income statement, most-recent period in the first column."""
        return self._call(lambda: yf.Ticker(symbol).financials, symbol)

    def _call(self, fetch: Any, symbol: str) -> Any:
        self._rate_limiter.acquire()

        retryer = Retrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._backoff_base_seconds),
            retry=retry_if_exception_type(Exception),
            reraise=False,
        )
        try:
            return retryer(fetch)
        except RetryError as exc:
            logger.error("Exhausted retries fetching %s from yfinance", symbol)
            raise DatafeedError(f"Failed to fetch '{symbol}' from yfinance") from exc
