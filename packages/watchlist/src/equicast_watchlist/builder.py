"""Build one system watchlist's entries by fetching each configured
instrument fresh from yfinance, via its own package's Client class
(equicast_fx.FXClient/equicast_future.FutureClient/
equicast_benchmark.BenchmarkClient) — this never reads any other
pipeline's already-published S3 output, so it doesn't depend on
fx/future/benchmark-ingestion.yml having run first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from equicast_benchmark import BenchmarkClient
from equicast_datafeed import DatafeedClient, round_value
from equicast_future import FutureClient
from equicast_fx import FXClient

from equicast_watchlist.config import WatchlistEntry

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
) -> list[dict[str, Any]]:
    """Build every configured entry, in config order regardless of fetch
    completion order (`ThreadPoolExecutor.map` preserves input order,
    unlike `as_completed`) — the watchlist's own display order shouldn't
    depend on which entry's yfinance calls happened to finish first."""
    if max_workers <= 1:
        return [build_entry(entry, datafeed) for entry in entries]

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda entry: build_entry(entry, datafeed), entries))
