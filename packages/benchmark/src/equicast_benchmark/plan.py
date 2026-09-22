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


def filter_benchmarks(benchmarks: list[Benchmark], keys: str | None) -> list[Benchmark]:
    """Restrict `benchmarks` to the given `;`-separated list of benchmark
    keys (case-insensitive), or return `benchmarks` unchanged when `keys`
    is empty — lets a manual run target specific benchmarks (e.g. for a
    full load) instead of every configured one."""
    if not keys:
        return benchmarks
    wanted = {key.strip().upper() for key in keys.split(";") if key.strip()}
    return [benchmark for benchmark in benchmarks if benchmark.key in wanted]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split the configured benchmarks into chunks for parallel processing."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to the benchmarks YAML.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=20,
        help="Target number of benchmarks per chunk (default: 20, chosen to keep the chunk "
        "count close to the ingest job's own max-parallel of 20 - see equicast-support#168).",
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
        help="Optional `;`-separated list of benchmark keys (e.g. 'SP500;FTSE100') to restrict "
        "the run to. Omit to run against every benchmark in --config.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    benchmarks = filter_benchmarks(load_benchmarks(args.config), args.tickers)
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
