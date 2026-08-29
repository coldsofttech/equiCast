"""CLI: extract a profile, daily prices, and risk metrics for every configured FX pair.

For each pair, all three are written as Parquet: one profile.parquet
snapshot, one price.parquet per year covered (just the current year by
default, or the pair's full yfinance history with --full-load), and one
metrics.parquet snapshot (volatility, Sharpe ratio, max drawdown, CAGR).
These three fetches for a given pair are independent tasks submitted to the
same worker pool, so they run concurrently rather than one after the other.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from equicast_datafeed import DatafeedClient
from equicast_metrics import MetricsClient

from equicast_fx.client import FXClient
from equicast_fx.config import FxPair, load_fx_pairs, parse_fx_pairs_json
from equicast_fx.writer import write_metrics_parquet, write_price_parquet, write_profile_parquet

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract FX pair profiles, daily prices, and risk metrics, "
        "writing all three as Parquet."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to an FX pairs YAML config.")
    source.add_argument(
        "--pairs-json",
        help='JSON array of {"from": ..., "to": ...} objects (e.g. one matrix chunk).',
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for Parquet files."
    )
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Fetch each pair's entire yfinance history instead of just the current year.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Profile/price/metrics fetches run concurrently, up to this many at once "
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


def _load_pairs(config: Path | None, pairs_json: str | None) -> list[FxPair]:
    if pairs_json is not None:
        return parse_fx_pairs_json(pairs_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_fx_pairs(config)


def _profile_task(client: FXClient, output_dir: Path, key: str) -> list[Path]:
    logger.info("Fetching profile for %s", key)
    return [write_profile_parquet(client.profile(), output_dir)]


def _prices_task(client: FXClient, output_dir: Path, key: str, full_load: bool) -> list[Path]:
    logger.info("Fetching prices for %s (full_load=%s)", key, full_load)
    return write_price_parquet(client.prices(full_load=full_load), output_dir)


def _metrics_task(
    metrics_client: MetricsClient,
    from_currency: str,
    to_currency: str,
    output_dir: Path,
    key: str,
) -> list[Path]:
    logger.info("Computing metrics for %s", key)
    metrics = metrics_client.metrics()
    return [write_metrics_parquet(metrics, from_currency, to_currency, output_dir)]


def run(
    config: Path | None,
    output_dir: Path,
    pairs_json: str | None = None,
    full_load: bool = False,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    pairs = _load_pairs(config, pairs_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    # One FXClient/MetricsClient per pair, shared by that pair's profile,
    # prices, and metrics tasks — all three only read immutable state and
    # delegate to the (thread-safe) shared datafeed, so calling them
    # concurrently on one instance is safe.
    tasks: list[Callable[[], list[Path]]] = []
    for pair in pairs:
        client = FXClient(pair.from_currency, pair.to_currency, datafeed=datafeed)
        metrics_client = MetricsClient(client.symbol, datafeed=datafeed)
        tasks.append(partial(_profile_task, client, output_dir, pair.key))
        tasks.append(partial(_prices_task, client, output_dir, pair.key, full_load))
        tasks.append(
            partial(
                _metrics_task,
                metrics_client,
                pair.from_currency,
                pair.to_currency,
                output_dir,
                pair.key,
            )
        )

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
        pairs_json=args.pairs_json,
        full_load=args.full_load,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
