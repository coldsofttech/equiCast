"""Build one system watchlist's entries by fetching each configured
instrument fresh from yfinance, via its own package's Client class
(equicast_fx.FXClient/equicast_future.FutureClient/
equicast_benchmark.BenchmarkClient/equicast_stock.StockClient/
equicast_etf.ETFClient) — this never reads any other pipeline's
already-published S3 output, so it doesn't depend on
fx/future/benchmark/stock/etf-ingestion.yml having run first.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from equicast_benchmark import BenchmarkClient
from equicast_datafeed import DatafeedClient, round_value
from equicast_etf import ETFClient
from equicast_future import FutureClient
from equicast_fx import FXClient
from equicast_stock import StockClient

from equicast_watchlist.config import WatchlistEntry

logger = logging.getLogger(__name__)

#: yfinance period covering both the 1-week and 1-month change windows in
#: one call per entry, rather than two separate get_history calls.
CHANGE_HISTORY_PERIOD = "1mo"

#: Trading days (not calendar days) back for the "1 week" change figure —
#: 5 trading days is the standard convention for a weekly change.
WEEK_LOOKBACK_TRADING_DAYS = 5


def _pct_change(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None or reference == 0:
        return None
    return round_value((current - reference) / reference * 100)


def _build_client(entry: WatchlistEntry, datafeed: DatafeedClient) -> Any:
    if entry.asset_class == "fx":
        return FXClient(entry.from_currency, entry.to_currency, datafeed=datafeed)
    if entry.asset_class == "future":
        return FutureClient(entry.key, entry.symbol, datafeed=datafeed)
    if entry.asset_class == "benchmark":
        return BenchmarkClient(entry.key, entry.symbol, datafeed=datafeed)
    # stock/etf entries never come from equicast_watchlist.config's explicit-entries
    # YAML (see its own ASSET_CLASSES — fx/future/benchmark only) — they're built
    # programmatically by equicast_watchlist.movers from the Top Winners/Top Losers
    # ranking, one WatchlistEntry per selected ticker.
    if entry.asset_class == "stock":
        return StockClient(entry.ticker, datafeed=datafeed)
    if entry.asset_class == "etf":
        return ETFClient(entry.ticker, datafeed=datafeed)
    raise ValueError(f"Unknown asset_class '{entry.asset_class}'.")


def build_entry(entry: WatchlistEntry, datafeed: DatafeedClient) -> dict[str, Any]:
    """Fetch `entry`'s profile and a month of daily history, returning one
    watchlist row: ticker/name/currency/current_price (native — never
    converted to any user's own currency, since a system watchlist has no
    single owner) and 1-week/1-month percent change. Any field that can't
    be computed (not enough history yet, yfinance has nothing for this
    symbol) comes back `None` rather than raising, so one bad symbol
    doesn't fail the whole watchlist build."""
    client = _build_client(entry, datafeed)
    profile = client.profile()
    name = profile.get("name") or profile.get("description") or entry.name
    currency = profile.get("currency") or profile.get("to_currency")
    current_price = profile.get("day_close")

    history = datafeed.get_history(client.symbol, period=CHANGE_HISTORY_PERIOD)
    week_ago_close = (
        float(history["Close"].iloc[-(WEEK_LOOKBACK_TRADING_DAYS + 1)])
        if len(history) > WEEK_LOOKBACK_TRADING_DAYS
        else None
    )
    month_ago_close = float(history["Close"].iloc[0]) if not history.empty else None

    return {
        "asset_class": entry.asset_class,
        "ticker": entry.ticker,
        "symbol": client.symbol,
        "name": name,
        "currency": currency,
        "current_price": current_price,
        "change_1w_pct": _pct_change(current_price, week_ago_close),
        "change_1m_pct": _pct_change(current_price, month_ago_close),
        "last_updated": profile.get("last_updated") or datetime.now(UTC).isoformat(),
        "source": "yfinance",
    }


def build_entries(
    entries: list[WatchlistEntry], datafeed: DatafeedClient, max_workers: int = 1
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build every configured entry, in config order regardless of fetch
    completion order — futures are submitted and then `.result()`-ed back
    in that same original order rather than via `as_completed`, so the
    watchlist's own display order doesn't depend on which entry's yfinance
    calls happened to finish first.

    `build_entry` itself only guards against a *missing* field within an
    otherwise-successful fetch (see its own docstring); an entry whose
    `client.profile()`/`get_history()` call raises outright (yfinance
    down, a bad symbol) is caught here instead, logged, and recorded in
    the returned failures list rather than aborting every other entry's
    build too — the same per-item resilience equicast-support#145 added
    to every other ingestion pipeline's `cli.run()`.
    """
    failures: list[dict[str, str]] = []

    def _record_failure(entry: WatchlistEntry, exc: Exception) -> None:
        logger.exception("Failed to build watchlist entry %s", entry.ticker)
        failures.append({"ticker": entry.ticker, "task": "profile", "error": str(exc)})

    built: list[dict[str, Any]] = []
    if max_workers <= 1:
        for entry in entries:
            try:
                built.append(build_entry(entry, datafeed))
            except Exception as exc:
                _record_failure(entry, exc)
        return built, failures

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(build_entry, entry, datafeed) for entry in entries]
        for entry, future in zip(entries, futures, strict=True):
            try:
                built.append(future.result())
            except Exception as exc:
                _record_failure(entry, exc)
    return built, failures
