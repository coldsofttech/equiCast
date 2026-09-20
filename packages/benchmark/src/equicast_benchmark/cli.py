"""CLI: extract a profile, daily prices, risk metrics, and news for every
configured benchmark.

For each benchmark, all four are written as Parquet: one profile.parquet
snapshot, one price.parquet per year covered (just the current year by
default, or the benchmark's full yfinance history with --full-load), one
metrics.parquet snapshot (volatility, Sharpe ratio, max drawdown, CAGR), and
a news.parquet of the benchmark's news articles from the trailing month
(omitted entirely when there's none - see equicast-news). These four
fetches for a given benchmark are independent tasks submitted to the same
worker pool, so they run concurrently rather than one after the other.
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
from equicast_news import NewsClient

from equicast_benchmark.client import BenchmarkClient
from equicast_benchmark.config import Benchmark, load_benchmarks, parse_benchmarks_json
from equicast_benchmark.writer import (
    write_failures_manifest,
    write_metrics_parquet,
    write_news_parquet,
    write_price_parquet,
    write_profile_parquet,
)

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract benchmark (market index) profiles, daily prices, and risk "
        "metrics, writing all three as Parquet."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to a benchmarks YAML config.")
    source.add_argument(
        "--benchmarks-json",
        help='JSON array of {"key": ..., "symbol": ...} objects (e.g. one matrix chunk).',
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for Parquet files."
    )
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Fetch each benchmark's entire yfinance history instead of just the current year.",
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


def _load_benchmarks(config: Path | None, benchmarks_json: str | None) -> list[Benchmark]:
    if benchmarks_json is not None:
        return parse_benchmarks_json(benchmarks_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_benchmarks(config)


def _profile_task(client: BenchmarkClient, output_dir: Path, key: str) -> list[Path]:
    logger.info("Fetching profile for %s", key)
    return [write_profile_parquet(client.profile(), output_dir)]


def _prices_task(
    client: BenchmarkClient, output_dir: Path, key: str, full_load: bool
) -> list[Path]:
    logger.info("Fetching prices for %s (full_load=%s)", key, full_load)
    return write_price_parquet(client.prices(full_load=full_load), output_dir)


def _metrics_task(
    metrics_client: MetricsClient,
    key: str,
    output_dir: Path,
) -> list[Path]:
    logger.info("Computing metrics for %s", key)
    metrics = metrics_client.metrics()
    return [write_metrics_parquet(metrics, key, output_dir)]


def _news_task(news_client: NewsClient, key: str, output_dir: Path) -> list[Path]:
    logger.info("Fetching news for %s", key)
    return write_news_parquet(news_client.news(), key, output_dir)


def run(
    config: Path | None,
    output_dir: Path,
    benchmarks_json: str | None = None,
    full_load: bool = False,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    benchmarks = _load_benchmarks(config, benchmarks_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    # One BenchmarkClient/MetricsClient/NewsClient per benchmark, shared by
    # that benchmark's profile, prices, metrics, and news tasks — all four
    # only read immutable state and delegate to the (thread-safe) shared
    # datafeed, so calling them concurrently on one instance is safe.
    #
    # Each task is tagged with its benchmark key and a short task label
    # (rather than a bare callable) so a failure below can be attributed
    # back to "which benchmark, which piece" for failures.json - see
    # equicast-support#145.
    tasks: list[tuple[str, str, Callable[[], list[Path]]]] = []
    for benchmark in benchmarks:
        client = BenchmarkClient(benchmark.key, benchmark.symbol, datafeed=datafeed)
        metrics_client = MetricsClient(client.symbol, datafeed=datafeed)
        news_client = NewsClient(client.symbol, datafeed=datafeed)
        tasks.append(
            (benchmark.key, "profile", partial(_profile_task, client, output_dir, benchmark.key))
        )
        tasks.append(
            (
                benchmark.key,
                "prices",
                partial(_prices_task, client, output_dir, benchmark.key, full_load),
            )
        )
        tasks.append(
            (
                benchmark.key,
                "metrics",
                partial(_metrics_task, metrics_client, benchmark.key, output_dir),
            )
        )
        tasks.append(
            (benchmark.key, "news", partial(_news_task, news_client, benchmark.key, output_dir))
        )

    # A failed task no longer aborts the whole run (previously, the first
    # future.result() to raise propagated straight out of this loop, losing
    # every other benchmark's already-fetched data too) - every other
    # benchmark's tasks still complete and get written/returned. Each
    # failure is instead collected into failures.json (equicast-support#145)
    # so the workflow can report exactly which benchmark/piece failed,
    # rather than the whole chunk.
    written: list[Path] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(task): (benchmark_key, task_label)
            for benchmark_key, task_label, task in tasks
        }
        for future in as_completed(future_to_task):
            benchmark_key, task_label = future_to_task[future]
            try:
                written.extend(future.result())
            except Exception as exc:
                logger.exception("Failed to fetch %s for %s", task_label, benchmark_key)
                failures.append({"ticker": benchmark_key, "task": task_label, "error": str(exc)})

    write_failures_manifest(failures, output_dir)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    for path in run(
        args.config,
        args.out,
        benchmarks_json=args.benchmarks_json,
        full_load=args.full_load,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
