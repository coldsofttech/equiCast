"""CLI: split the configured futures into chunks for parallel processing.

Used by the future-ingestion workflow's "plan" job to decide how many
parallel matrix legs to run. GitHub Actions caps a single workflow's matrix
at 256 jobs, so --max-chunks defaults to that ceiling: if the futures list
is larger than chunk_size * max_chunks, the effective chunk size grows to
still fit within max_chunks rather than silently dropping futures.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from equicast_future.config import Future, load_futures

GITHUB_ACTIONS_MAX_MATRIX_JOBS = 256


def chunk_futures(futures: list[Future], chunk_size: int, max_chunks: int) -> list[list[Future]]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if max_chunks < 1:
        raise ValueError("max_chunks must be at least 1")
    if not futures:
        return []

    effective_size = max(chunk_size, math.ceil(len(futures) / max_chunks))
    return [futures[i : i + effective_size] for i in range(0, len(futures), effective_size)]


def filter_futures(futures: list[Future], keys: str | None) -> list[Future]:
    """Restrict `futures` to the given `;`-separated list of future keys
    (case-insensitive), or return `futures` unchanged when `keys` is empty
    — lets a manual run target specific futures (e.g. for a full load)
    instead of every configured one."""
    if not keys:
        return futures
    wanted = {key.strip().upper() for key in keys.split(";") if key.strip()}
    return [future for future in futures if future.key in wanted]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split the configured futures into chunks for parallel processing."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to the futures YAML.")
    parser.add_argument(
        "--chunk-size", type=int, default=300, help="Target number of futures per chunk."
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=GITHUB_ACTIONS_MAX_MATRIX_JOBS,
        help="Hard cap on the number of chunks (GitHub Actions allows at most 256 matrix jobs).",
    )
    parser.add_argument(
        "--tickers",
        default=None,
        help="Optional `;`-separated list of future keys (e.g. 'GOLD;CRUDE_OIL_WTI') to "
        "restrict the run to. Omit to run against every future in --config.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    futures = filter_futures(load_futures(args.config), args.tickers)
    chunks = chunk_futures(futures, args.chunk_size, args.max_chunks)

    print(
        json.dumps(
            [
                [{"key": future.key, "symbol": future.symbol} for future in chunk]
                for chunk in chunks
            ]
        )
    )


if __name__ == "__main__":
    main()
