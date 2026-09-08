"""CLI: build one system watchlist's entries fresh from yfinance and write
them as Parquet.

Three modes, one binary:

- `--mode config` (default, unchanged): fx/future/benchmark entries listed
  in a config YAML — Global Markets. No "plan" job splitting work into
  matrix chunks here either: one system watchlist's entry list is small
  enough (today: 24 for Global Markets) to fetch in a single container run.
- `--mode rank`: step 1 of Top Winners/Top Losers — every stock/ETF
  ticker's trailing 1-year CAGR, written as a plain JSON ranking file (see
  equicast_watchlist.movers).
- `--mode movers`: steps 2/3 of Top Winners/Top Losers — read that ranking
  file, keep the top (or bottom) `--limit` tickers, and build their full
  watchlist entries the same way `--mode config` does.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from equicast_datafeed import DatafeedClient

from equicast_watchlist.builder import build_entries
from equicast_watchlist.config import load_watchlist_entries
from equicast_watchlist.movers import (
    compute_cagr_rankings,
    load_rankings,
    merge_change_1y,
    select_top,
    to_watchlist_entries,
    write_rankings,
)
from equicast_watchlist.writer import write_entries_parquet

logger = logging.getLogger(__name__)

#: Default cap on how many tickers `--mode movers` builds full entries for
#: — overridden in CI via the `MAX_HOLDINGS_FOR_WATCHLIST` repo variable
#: (see .github/workflows/watchlist-ingestion.yml), same variable
#: backend/watchlists/views.py's HoldingsClient reads for a custom
#: watchlist's own holdings cap.
DEFAULT_MOVERS_LIMIT = 50


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build one system watchlist's entries fresh from yfinance, writing "
        "them as one Parquet file — fx/future/benchmark entries from a config YAML "
        "(--mode config), a stock/ETF 1-year-CAGR ranking (--mode rank), or that "
        "ranking's top/bottom N as full watchlist entries (--mode movers)."
    )
    parser.add_argument(
        "--mode",
        choices=("config", "rank", "movers"),
        default="config",
        help='"config" (default): fx/future/benchmark entries from --config. "rank": '
        "every stock/ETF ticker's trailing 1-year CAGR, from --stock-config/--etf-config. "
        '"movers": --rankings\' top/bottom --limit tickers as full watchlist entries.',
    )
    parser.add_argument(
        "--watchlist-key",
        help='S3 partition key this watchlist lands under (watchlist=<KEY>/...), e.g. '
        '"GLOBAL_MARKETS"/"TOP_WINNERS"/"TOP_LOSERS". Required for --mode config/movers.',
    )
    parser.add_argument(
        "--config", type=Path, help="Path to this watchlist's entries YAML. Required for --mode config."
    )
    parser.add_argument(
        "--stock-config", type=Path, help="Path to equicast-stock's tickers YAML. Required for --mode rank."
    )
    parser.add_argument(
        "--etf-config", type=Path, help="Path to equicast-etf's tickers YAML. Required for --mode rank."
    )
    parser.add_argument(
        "--direction",
        choices=("winners", "losers"),
        help="Which side of the ranking to keep. Required for --mode movers.",
    )
    parser.add_argument(
        "--rankings", type=Path, help="Path to --mode rank's output JSON. Required for --mode movers."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_MOVERS_LIMIT,
        help=f"Max entries to build for --mode movers (default: {DEFAULT_MOVERS_LIMIT}).",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for the Parquet/JSON file."
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
    """`--mode config`: fx/future/benchmark entries from a config YAML."""
    entries = load_watchlist_entries(config)
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)
    built = build_entries(entries, datafeed, max_workers=max_workers)
    return write_entries_parquet(watchlist_key, built, output_dir)


def run_rank(
    stock_config: Path,
    etf_config: Path,
    output_dir: Path,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> Path:
    """`--mode rank`: step 1 — every stock/ETF ticker's trailing 1-year CAGR,
    written to `<output_dir>/rankings.json`."""
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)
    rankings = compute_cagr_rankings(stock_config, etf_config, datafeed, max_workers=max_workers)
    return write_rankings(rankings, output_dir / "rankings.json")


def run_movers(
    watchlist_key: str,
    direction: str,
    rankings_path: Path,
    limit: int,
    output_dir: Path,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> Path:
    """`--mode movers`: steps 2/3 — `--mode rank`'s top/bottom `limit`
    tickers, built into full watchlist entries the same way `run` does."""
    selected = select_top(load_rankings(rankings_path), direction, limit)
    entries = to_watchlist_entries(selected)
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)
    built = build_entries(entries, datafeed, max_workers=max_workers)
    merge_change_1y(built, selected)
    return write_entries_parquet(watchlist_key, built, output_dir)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.mode == "config":
        if not args.watchlist_key or not args.config:
            parser.error("--mode config requires --watchlist-key and --config.")
        path = run(
            args.watchlist_key,
            args.config,
            args.out,
            max_workers=args.max_workers,
            max_calls=args.max_calls,
            period_seconds=args.period_seconds,
        )
    elif args.mode == "rank":
        if not args.stock_config or not args.etf_config:
            parser.error("--mode rank requires --stock-config and --etf-config.")
        path = run_rank(
            args.stock_config,
            args.etf_config,
            args.out,
            max_workers=args.max_workers,
            max_calls=args.max_calls,
            period_seconds=args.period_seconds,
        )
    else:
        if not args.watchlist_key or not args.direction or not args.rankings:
            parser.error("--mode movers requires --watchlist-key, --direction, and --rankings.")
        path = run_movers(
            args.watchlist_key,
            args.direction,
            args.rankings,
            args.limit,
            args.out,
            max_workers=args.max_workers,
            max_calls=args.max_calls,
            period_seconds=args.period_seconds,
        )
    print(path)


if __name__ == "__main__":
    main()
