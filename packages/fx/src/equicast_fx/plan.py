"""CLI: split the configured FX pairs into chunks for parallel processing.

Used by the fx-ingestion workflow's "plan" job to decide how many parallel
matrix legs to run. GitHub Actions caps a single workflow's matrix at 256
jobs, so --max-chunks defaults to that ceiling: if the pair list is larger
than chunk_size * max_chunks, the effective chunk size grows to still fit
within max_chunks rather than silently dropping pairs.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from equicast_fx.config import FxPair, load_fx_pairs

GITHUB_ACTIONS_MAX_MATRIX_JOBS = 256


def chunk_pairs(pairs: list[FxPair], chunk_size: int, max_chunks: int) -> list[list[FxPair]]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if max_chunks < 1:
        raise ValueError("max_chunks must be at least 1")
    if not pairs:
        return []

    effective_size = max(chunk_size, math.ceil(len(pairs) / max_chunks))
    return [pairs[i : i + effective_size] for i in range(0, len(pairs), effective_size)]


def filter_pairs(pairs: list[FxPair], keys: str | None) -> list[FxPair]:
    """Restrict `pairs` to the given `;`-separated list of pair keys (e.g.
    'GBPUSD;EURUSD', case-insensitive), or return `pairs` unchanged when
    `keys` is empty — lets a manual run target specific pairs (e.g. for a
    full load) instead of every configured pair."""
    if not keys:
        return pairs
    wanted = {key.strip().upper() for key in keys.split(";") if key.strip()}
    return [pair for pair in pairs if pair.key in wanted]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split the configured FX pairs into chunks for parallel processing."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to the FX pairs YAML.")
    parser.add_argument(
        "--chunk-size", type=int, default=300, help="Target number of pairs per chunk."
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
        help="Optional `;`-separated list of pair keys (e.g. 'GBPUSD;EURUSD') to restrict the "
        "run to. Omit to run against every pair in --config.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    pairs = filter_pairs(load_fx_pairs(args.config), args.tickers)
    chunks = chunk_pairs(pairs, args.chunk_size, args.max_chunks)

    print(
        json.dumps(
            [
                [{"from": pair.from_currency, "to": pair.to_currency} for pair in chunk]
                for chunk in chunks
            ]
        )
    )


if __name__ == "__main__":
    main()
