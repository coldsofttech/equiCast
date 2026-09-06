"""CLI: extract a profile, daily prices, dividends, events, and metrics for
every configured stock ticker.

For each ticker, writes one profile.parquet snapshot (including a
`dividend_frequency` field derived from dividend history - see
`equicast_dividends.dividend_frequency`), a price/current.parquet and
dividend/current.parquet (plus price/history.parquet and
dividend/history.parquet too, but only on a --full-load run), an
events/current.parquet (and events/history.parquet on --full-load), and one
metrics.parquet snapshot combining equicast-metrics' risk/performance
metrics (volatility, Sharpe ratio, max drawdown, CAGR) with its stock-only
valuation/fundamental metrics (PE, EPS, margins, returns, leverage,
FCF/share). Profile and dividends are fetched together as one task (both
need the same dividend history - see `_profile_and_dividends_task`); prices,
events, and metrics are three further independent tasks - all four for a
given ticker submitted to the same worker pool, so they run concurrently
rather than one after the other.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from equicast_datafeed import DatafeedClient
from equicast_dividends import DividendsClient, dividend_frequency
from equicast_events import EventsClient
from equicast_metrics import MetricsClient

from equicast_stock.client import StockClient
from equicast_stock.config import StockTicker, load_stock_tickers, parse_stock_tickers_json
from equicast_stock.writer import (
    write_dividend_parquet,
    write_events_parquet,
    write_metrics_parquet,
    write_price_parquet,
    write_profile_parquet,
)

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract stock ticker profiles, daily prices, dividends, events, and "
        "metrics, writing all five as Parquet."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to a stock tickers YAML config.")
    source.add_argument(
        "--tickers-json",
        help="JSON array of ticker strings (e.g. one matrix chunk).",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for Parquet files."
    )
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Fetch each ticker's entire yfinance history (prices, dividends, and events) "
        "instead of just the current year.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Profile/price/dividend/events/metrics fetches run concurrently, up to this many "
        "at once (default: 1).",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=1,
        help="Max yfinance calls allowed per --period-seconds, shared across all workers.",
    )
    parser.add_argument(
        "--period-seconds",
        type=float,
        default=1.0,
        help="Rate-limit window, in seconds (default: 1.0).",
    )
    return parser


def _load_tickers(config: Path | None, tickers_json: str | None) -> list[StockTicker]:
    if tickers_json is not None:
        return parse_stock_tickers_json(tickers_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_stock_tickers(config)


def _profile_and_dividends_task(
    client: StockClient,
    dividends_client: DividendsClient,
    output_dir: Path,
    key: str,
    full_load: bool,
) -> list[Path]:
    """Write profile.parquet (with a `dividend_frequency` field derived from
    dividend history) and dividend/current.parquet (plus
    dividend/history.parquet on a --full-load run).

    Combined into one task, rather than two independent ones like
    prices/events, because both need the same dividend history:
    `DividendsClient.dividends()` fetches this ticker's *entire* yfinance
    dividend series regardless of its own `full_load` argument — that flag
    only controls a post-fetch filter (see its docstring) — so calling it
    once with `full_load=True` here and filtering client-side for what to
    write costs no more yfinance calls than the old separate profile/
    dividends tasks did, while a naive merge that just called `dividends()`
    a second time from `_profile_task` would have doubled them.
    """
    logger.info("Fetching profile and dividends for %s (full_load=%s)", key, full_load)
    dividends = dividends_client.dividends(full_load=True)
    profile = {**client.profile(), "dividend_frequency": dividend_frequency(dividends)}
    paths = [write_profile_parquet(profile, output_dir)]

    if full_load:
        to_write = dividends
    else:
        current_year = str(datetime.now(UTC).year)
        to_write = [d for d in dividends if d["ex_dividend_date"][:4] == current_year]
    paths.extend(write_dividend_parquet(to_write, output_dir))
    return paths


def _prices_task(client: StockClient, output_dir: Path, key: str, full_load: bool) -> list[Path]:
    logger.info("Fetching prices for %s (full_load=%s)", key, full_load)
    return write_price_parquet(client.prices(full_load=full_load), output_dir)


def _events_task(
    events_client: EventsClient, output_dir: Path, key: str, full_load: bool
) -> list[Path]:
    logger.info("Fetching events for %s (full_load=%s)", key, full_load)
    return write_events_parquet(events_client.events(full_load=full_load), output_dir)


def _combine_metrics(risk_metrics: dict[str, Any], fundamentals: dict[str, Any]) -> dict[str, Any]:
    """Merge MetricsClient.metrics() (risk/performance) and .fundamentals()
    (valuation) into one metrics.parquet record.

    Both compute their own last_updated/source independently (fetched
    moments apart), so this reconciles the two into a single pair of each
    rather than keeping duplicate keys.
    """
    combined = {**risk_metrics, **fundamentals}
    combined["last_updated"] = max(risk_metrics["last_updated"], fundamentals["last_updated"])
    combined["source"] = (
        "equicast" if "equicast" in (risk_metrics["source"], fundamentals["source"]) else "yfinance"
    )
    return combined


def _metrics_task(metrics_client: MetricsClient, output_dir: Path, key: str) -> list[Path]:
    logger.info("Computing metrics for %s", key)
    combined = _combine_metrics(metrics_client.metrics(), metrics_client.fundamentals())
    return [write_metrics_parquet(combined, metrics_client.symbol, output_dir)]


def run(
    config: Path | None,
    output_dir: Path,
    tickers_json: str | None = None,
    full_load: bool = False,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    tickers = _load_tickers(config, tickers_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    # One StockClient/MetricsClient/DividendsClient/EventsClient per ticker,
    # shared by that ticker's profile+dividends, prices, events, and metrics
    # tasks — all four only read immutable state and delegate to the
    # (thread-safe) shared datafeed, so calling them concurrently on one
    # instance is safe.
    tasks: list[Callable[[], list[Path]]] = []
    for ticker in tickers:
        client = StockClient(ticker.ticker, datafeed=datafeed)
        metrics_client = MetricsClient(client.symbol, datafeed=datafeed)
        dividends_client = DividendsClient(client.symbol, datafeed=datafeed)
        events_client = EventsClient(client.symbol, datafeed=datafeed)
        tasks.append(
            partial(
                _profile_and_dividends_task,
                client,
                dividends_client,
                output_dir,
                ticker.key,
                full_load,
            )
        )
        tasks.append(partial(_prices_task, client, output_dir, ticker.key, full_load))
        tasks.append(partial(_events_task, events_client, output_dir, ticker.key, full_load))
        tasks.append(partial(_metrics_task, metrics_client, output_dir, ticker.key))

    written: list[Path] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in as_completed(futures):
            written.extend(future.result())
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    for path in run(
        args.config,
        args.out,
        tickers_json=args.tickers_json,
        full_load=args.full_load,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
