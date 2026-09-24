"""Resilient client around yfinance: rate limiting, retry-with-backoff, and
per-run caching."""

from __future__ import annotations

import logging
import threading
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
    """Fetches ticker info and history from yfinance with limits and retries.

    Every fetch is cached for this instance's lifetime, keyed by (method,
    symbol, ...distinguishing args e.g. period) - see `_call`'s docstring.
    equicast-stock/etf/fx/benchmark and equicast-metrics/dividends/events
    each construct their own per-ticker client (StockClient, MetricsClient,
    ...) but share one DatafeedClient across every ticker's tasks in a run
    (see e.g. equicast_stock.cli.run), so this transparently dedupes calls
    like `.info` that several of those tasks fetch independently for the
    same ticker (equicast-support#168) without any of them needing to know
    caching exists.
    """

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
        self._cache: dict[tuple[Any, ...], Any] = {}
        #: One lock per cache key, created on first use - lets concurrent
        #: first-time requests for the *same* key (e.g. two tasks for the
        #: same ticker both wanting `.info`) block on each other rather than
        #: both racing to fetch it, while requests for different keys never
        #: block each other. `_cache_locks_guard` only ever protects this
        #: dict's own get-or-create, never the (potentially slow) fetch
        #: itself.
        self._cache_locks: dict[tuple[Any, ...], threading.Lock] = {}
        self._cache_locks_guard = threading.Lock()

    def get_info(self, symbol: str) -> dict[str, Any]:
        """Return the `.info` dict yfinance reports for `symbol`."""
        return self._call(lambda: yf.Ticker(symbol).info, symbol, ("info", symbol))

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """Return historical OHLCV data for `symbol`."""
        return self._call(
            lambda: yf.Ticker(symbol).history(period=period, interval=interval),
            symbol,
            ("history", symbol, period, interval),
        )

    def get_isin(self, symbol: str) -> str | None:
        """Return `symbol`'s ISIN, or `None` if yfinance has none on record
        (it reports the literal string "-" in that case)."""
        isin = self._call(lambda: yf.Ticker(symbol).isin, symbol, ("isin", symbol))
        return isin if isin and isin != "-" else None

    def get_dividends(self, symbol: str) -> pd.Series:
        """Return `symbol`'s historical dividends: a Series of cash amount per
        share, indexed by ex-dividend date. yfinance has no payment-date data
        here - only ex-dividend date and amount."""
        return self._call(lambda: yf.Ticker(symbol).dividends, symbol, ("dividends", symbol))

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """Return `symbol`'s annual balance sheet, most-recent period in the first column."""
        return self._call(
            lambda: yf.Ticker(symbol).balance_sheet, symbol, ("balance_sheet", symbol)
        )

    def get_financials(self, symbol: str) -> pd.DataFrame:
        """Return `symbol`'s annual income statement, most-recent period in the first column."""
        return self._call(lambda: yf.Ticker(symbol).financials, symbol, ("financials", symbol))

    def get_earnings_dates(self, symbol: str, limit: int = 12) -> pd.DataFrame:
        """Return up to `limit` of `symbol`'s earnings dates (yfinance caps
        this at 100), indexed by earnings date, mixing already-reported rows
        (EPS Estimate/Reported EPS/Surprise(%) all populated) with upcoming
        estimated ones (Reported EPS/Surprise(%) still NaN) - yfinance has no
        separate call for each, only this one combined, most-recent-first
        list capped by row count rather than a date range."""
        return self._call(
            lambda: yf.Ticker(symbol).get_earnings_dates(limit=limit),
            symbol,
            ("earnings_dates", symbol, limit),
        )

    def get_upgrades_downgrades(self, symbol: str) -> pd.DataFrame:
        """Return `symbol`'s full analyst rating-change history reported by
        yfinance (firm, from/to grade, action), indexed by grade date. This
        is inherently a historical log - each row is a past rating-change
        event - so there's no forward-looking equivalent the way earnings
        dates has estimated future rows."""
        return self._call(
            lambda: yf.Ticker(symbol).upgrades_downgrades,
            symbol,
            ("upgrades_downgrades", symbol),
        )

    def get_splits(self, symbol: str) -> pd.Series:
        """Return `symbol`'s historical stock splits: a Series of split
        ratio (e.g. 4.0 for a 4-for-1 split, 0.5 for a 1-for-2 reverse
        split), indexed by split date."""
        return self._call(lambda: yf.Ticker(symbol).splits, symbol, ("splits", symbol))

    def get_news(
        self, symbol: str, count: int = 50, tab: str = "news"
    ) -> list[dict[str, Any]]:
        """Return up to `count` of `symbol`'s most recent news articles
        (yfinance's own newest-first order), each a raw, nested dict (not a
        DataFrame - unlike every other method here, this is yfinance's only
        list-of-dicts-shaped call). No date-range parameter exists on
        yfinance's side; a caller wanting only the trailing N days filters
        the returned `content.pubDate` values itself (see
        `equicast_news.NewsClient`).

        `tab` is yfinance's own `get_news(tab=...)` parameter ("news" by
        default, matching yfinance's own default) - `equicast_news.NewsClient`
        requests "all" instead (see its own docstring for why)."""
        return self._call(
            lambda: yf.Ticker(symbol).get_news(count=count, tab=tab),
            symbol,
            ("news", symbol, count, tab),
        )

    def _call(self, fetch: Any, symbol: str, cache_key: tuple[Any, ...]) -> Any:
        """Fetch-through cache: `cache_key` (method name plus symbol plus
        any args that change what's returned, e.g. `get_history`'s period/
        interval - see each caller above) identifies this exact request for
        this `DatafeedClient`'s lifetime. A cache hit returns immediately,
        without touching the rate limiter - it isn't a new yfinance call.
        A failure (after `_call_uncached`'s own retries are exhausted) is
        cached too and re-raised to every caller of that key, rather than
        having each one separately re-run the same doomed retry sequence.
        """
        with self._cache_locks_guard:
            lock = self._cache_locks.setdefault(cache_key, threading.Lock())

        with lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                if isinstance(cached, DatafeedError):
                    raise cached
                return cached

            try:
                result = self._call_uncached(fetch, symbol)
            except DatafeedError as exc:
                self._cache[cache_key] = exc
                raise
            self._cache[cache_key] = result
            return result

    def _call_uncached(self, fetch: Any, symbol: str) -> Any:
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
