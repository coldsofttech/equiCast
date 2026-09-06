"""CLI: split the configured benchmarks into chunks for parallel processing.

Used by the benchmark-ingestion workflow's "plan" job to decide how many
parallel matrix legs to run. GitHub Actions caps a single workflow's matrix
at 256 jobs, so --max-chunks defaults to that ceiling: if the benchmark list
is larger than chunk_size * max_chunks, the effective chunk size grows to
still fit within max_chunks rather than silently dropping benchmarks.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from equicast_benchmark.config import Benchmark, load_benchmarks

GITHUB_ACTIONS_MAX_MATRIX_JOBS = 256


def chunk_benchmarks(
    benchmarks: list[Benchmark], chunk_size: int, max_chunks: int
) -> list[list[Benchmark]]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if max_chunks < 1:
        raise ValueError("max_chunks must be at least 1")
    if not benchmarks:
        return []

    effective_size = max(chunk_size, math.ceil(len(benchmarks) / max_chunks))
    return [benchmarks[i : i + effective_size] for i in range(0, len(benchmarks), effective_size)]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split the configured benchmarks into chunks for parallel processing."
    )
    parser.add_argument(
        "--config", type=Path, required=True, help="Path to the benchmarks YAML."
    )
    parser.add_argument(
        "--chunk-size", type=int, default=300, help="Target number of benchmarks per chunk."
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=GITHUB_ACTIONS_MAX_MATRIX_JOBS,
        help="Hard cap on the number of chunks (GitHub Actions allows at most 256 matrix jobs).",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    benchmarks = load_benchmarks(args.config)
    chunks = chunk_benchmarks(benchmarks, args.chunk_size, args.max_chunks)

    print(
        json.dumps(
            [
                [{"key": benchmark.key, "symbol": benchmark.symbol} for benchmark in chunk]
                for chunk in chunks
            ]
        )
    )


if __name__ == "__main__":
    main()
