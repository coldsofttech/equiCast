"""CLI: extract a profile, daily prices, and dividends for every configured
ETF ticker.

For each ticker, writes one profile.parquet snapshot and one price.parquet/
dividend.parquet per year covered (just the current year by default, or the
ticker's full yfinance history with --full-load). No events/metrics yet,
unlike equicast-stock, so there are three tasks per ticker rather than five.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from equicast_datafeed import DatafeedClient
from equicast_dividends import DividendsClient

from equicast_etf.client import ETFClient
from equicast_etf.config import ETFTicker, load_etf_tickers, parse_etf_tickers_json
from equicast_etf.writer import (
    write_dividend_parquet,
    write_price_parquet,
    write_profile_parquet,
)

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract ETF ticker profiles, daily prices, and dividends, writing all "
        "three as Parquet."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to an ETF tickers YAML config.")
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
        help="Fetch each ticker's entire yfinance history instead of just the current year.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Profile/price/dividends fetches run concurrently, up to this many at once "
        "(default: 1).",
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


def _load_tickers(config: Path | None, tickers_json: str | None) -> list[ETFTicker]:
    if tickers_json is not None:
        return parse_etf_tickers_json(tickers_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_etf_tickers(config)


def _profile_task(client: ETFClient, output_dir: Path, key: str) -> list[Path]:
    logger.info("Fetching profile for %s", key)
    return [write_profile_parquet(client.profile(), output_dir)]


def _prices_task(client: ETFClient, output_dir: Path, key: str, full_load: bool) -> list[Path]:
    logger.info("Fetching prices for %s (full_load=%s)", key, full_load)
    return write_price_parquet(client.prices(full_load=full_load), output_dir)


def _dividends_task(
    dividends_client: DividendsClient, output_dir: Path, key: str, full_load: bool
) -> list[Path]:
    logger.info("Fetching dividends for %s (full_load=%s)", key, full_load)
    return write_dividend_parquet(dividends_client.dividends(full_load=full_load), output_dir)


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

    # One ETFClient/DividendsClient per ticker, shared by that ticker's
    # profile, prices, and dividends tasks — all three only read immutable
    # state and delegate to the (thread-safe) shared datafeed, so calling
    # them concurrently on one instance is safe.
    tasks: list[Callable[[], list[Path]]] = []
    for ticker in tickers:
        client = ETFClient(ticker.ticker, datafeed=datafeed)
        dividends_client = DividendsClient(client.symbol, datafeed=datafeed)
        tasks.append(partial(_profile_task, client, output_dir, ticker.key))
        tasks.append(partial(_prices_task, client, output_dir, ticker.key, full_load))
        tasks.append(partial(_dividends_task, dividends_client, output_dir, ticker.key, full_load))

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
