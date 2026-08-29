"""CLI: extract a profile for every configured FX pair and write it as Parquet."""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from equicast_datafeed import DatafeedClient

from equicast_fx.client import FXClient
from equicast_fx.config import FxPair, load_fx_pairs, parse_fx_pairs_json
from equicast_fx.writer import write_profile_parquet

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract FX pair profiles and write them as Parquet."
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
        "--max-workers",
        type=int,
        default=1,
        help="FX pairs fetched concurrently (default: 1, sequential).",
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


def _extract_one(pair: FxPair, datafeed: DatafeedClient, output_dir: Path) -> Path:
    logger.info("Fetching profile for %s", pair.key)
    profile = FXClient(pair.from_currency, pair.to_currency, datafeed=datafeed).profile()
    return write_profile_parquet(profile, output_dir)


def run(
    config: Path | None,
    output_dir: Path,
    pairs_json: str | None = None,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    pairs = _load_pairs(config, pairs_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_extract_one, pair, datafeed, output_dir) for pair in pairs]
        return [future.result() for future in as_completed(futures)]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    for path in run(
        args.config,
        args.out,
        pairs_json=args.pairs_json,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
