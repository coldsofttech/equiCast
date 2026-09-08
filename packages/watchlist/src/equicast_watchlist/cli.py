"""CLI: build one system watchlist's entries fresh from yfinance and write
them as Parquet.

Unlike equicast-fx/-stock/-etf/-benchmark/-future, this never touches S3
for reads — every entry comes straight from yfinance via its own package's
Client class (see equicast_watchlist.builder) — so there's no "plan" job
splitting work into matrix chunks: one system watchlist's entry list is
small enough (today: 24 for Global Markets) to fetch in a single container
run.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from equicast_datafeed import DatafeedClient

from equicast_watchlist.builder import build_entries
from equicast_watchlist.config import load_watchlist_entries
from equicast_watchlist.writer import write_entries_parquet

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one system watchlist's entries (fx pairs, futures, benchmarks) "
        "fresh from yfinance, writing them as one Parquet file."
    )
    parser.add_argument(
        "--watchlist-key",
        required=True,
        help='S3 partition key this watchlist lands under (watchlist=<KEY>/...), e.g. '
        '"GLOBAL_MARKETS".',
    )
    parser.add_argument(
        "--config", type=Path, required=True, help="Path to this watchlist's entries YAML."
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for the Parquet file."
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Entries are fetched concurrently, up to this many at once (default: 1).",
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


def run(
    watchlist_key: str,
    config: Path,
    output_dir: Path,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> Path:
    entries = load_watchlist_entries(config)
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)
    built = build_entries(entries, datafeed, max_workers=max_workers)
    return write_entries_parquet(watchlist_key, built, output_dir)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    path = run(
        args.watchlist_key,
        args.config,
        args.out,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    )
    print(path)


if __name__ == "__main__":
    main()
