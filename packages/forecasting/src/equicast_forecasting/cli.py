"""CLI: forecast future dividend payouts for every configured ticker.

For each ticker, fetches its full dividend history via `DividendsClient`,
projects it forward with `equicast_forecasting.dividends()`, and writes
`<asset_class>=<TICKER>/forecasting/dividends.parquet` — nothing at all for
a ticker with no dependable cadence to forecast (an
"irregular"/"not_applicable" payer). Each ticker's fetch-and-forecast is an
independent task submitted to the same worker pool, so they run
concurrently rather than one after the other.

Fetches its own dividend history live via `equicast-dividends`
(`DividendsClient.dividends(full_load=True)`), the same call
`equicast-stock`/`equicast-etf`'s own ingestion already makes for
`dividend.parquet` — this is a second, independent fetch, not a read-back
of what that pipeline already wrote to S3.
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

from equicast_forecasting.config import load_tickers, parse_tickers_json
from equicast_forecasting.forecast import dividends
from equicast_forecasting.writer import write_dividend_forecast_parquet

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forecast each configured ticker's future dividend payouts from its "
        "actual ex-dividend-date history, writing one dividends.parquet per ticker."
    )
    parser.add_argument(
        "--asset-class",
        required=True,
        choices=["stock", "etf"],
        help="Determines the S3 key prefix written to (stock=<TICKER>/... or etf=<TICKER>/...).",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to a tickers YAML config.")
    source.add_argument(
        "--tickers-json",
        help="JSON array of ticker strings (e.g. one matrix chunk).",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for Parquet files."
    )
    parser.add_argument(
        "--years",
        type=int,
        default=10,
        help="Forecast horizon in years (default: 10).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Ticker fetch-and-forecast tasks run concurrently, up to this many at once "
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


def _load_tickers(config: Path | None, tickers_json: str | None) -> list[str]:
    if tickers_json is not None:
        return parse_tickers_json(tickers_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_tickers(config)


def _forecast_task(
    ticker: str, datafeed: DatafeedClient, output_dir: Path, asset_class: str, years: int
) -> Path | None:
    logger.info("Forecasting dividends for %s", ticker)
    dividends_client = DividendsClient(ticker, datafeed=datafeed)
    history = dividends_client.dividends(full_load=True)
    forecast = dividends(history, years=years)
    return write_dividend_forecast_parquet(forecast, output_dir, asset_class)


def run(
    asset_class: str,
    config: Path | None,
    output_dir: Path,
    tickers_json: str | None = None,
    years: int = 10,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    tickers = _load_tickers(config, tickers_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    tasks: list[Callable[[], Path | None]] = [
        partial(_forecast_task, ticker, datafeed, output_dir, asset_class, years)
        for ticker in tickers
    ]

    written: list[Path] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in as_completed(futures):
            path = future.result()
            if path is not None:
                written.append(path)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    for path in run(
        args.asset_class,
        args.config,
        args.out,
        tickers_json=args.tickers_json,
        years=args.years,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
