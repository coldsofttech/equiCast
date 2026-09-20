"""CLI: split the configured ETF tickers into chunks for parallel processing.

Used by the etf-ingestion workflow's "plan" job to decide how many parallel
matrix legs to run. GitHub Actions caps a single workflow's matrix at 256
jobs, so --max-chunks defaults to that ceiling: if the ticker list is larger
than chunk_size * max_chunks, the effective chunk size grows to still fit
within max_chunks rather than silently dropping tickers.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from equicast_etf.config import ETFTicker, load_etf_tickers

GITHUB_ACTIONS_MAX_MATRIX_JOBS = 256


def chunk_tickers(
    tickers: list[ETFTicker], chunk_size: int, max_chunks: int
) -> list[list[ETFTicker]]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if max_chunks < 1:
        raise ValueError("max_chunks must be at least 1")
    if not tickers:
        return []

    effective_size = max(chunk_size, math.ceil(len(tickers) / max_chunks))
    return [tickers[i : i + effective_size] for i in range(0, len(tickers), effective_size)]


def filter_tickers(tickers: list[ETFTicker], keys: str | None) -> list[ETFTicker]:
    """Restrict `tickers` to the given `;`-separated list of ticker keys
    (case-insensitive), or return `tickers` unchanged when `keys` is empty —
    lets a manual run target just-added holdings (e.g. for a full load)
    instead of every configured ticker."""
    if not keys:
        return tickers
    wanted = {key.strip().upper() for key in keys.split(";") if key.strip()}
    return [ticker for ticker in tickers if ticker.key in wanted]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split the configured ETF tickers into chunks for parallel processing."
    )
    parser.add_argument("--config", type=Path, required=True, help="Path to the ETF tickers YAML.")
    parser.add_argument(
        "--chunk-size", type=int, default=300, help="Target number of tickers per chunk."
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
        help="Optional `;`-separated list of tickers (e.g. 'AAPL;MSFT') to restrict the run to. "
        "Omit to run against every ticker in --config.",
    )
    return parser


def _serialize_ticker(ticker: ETFTicker) -> str | dict:
    """Plain ticker string when there's no ISIN/tax_domicile override, else
    a `{ticker, isin, tax_domicile}` mapping (only the overrides actually
    set) — round-trips through `parse_etf_tickers_json` (via
    `_tickers_from_raw`) so an override in the config survives being split
    into a GitHub Actions matrix chunk."""
    overrides = {
        k: v for k, v in {"isin": ticker.isin, "tax_domicile": ticker.tax_domicile}.items() if v
    }
    return {"ticker": ticker.ticker, **overrides} if overrides else ticker.ticker


def main() -> None:
    args = build_arg_parser().parse_args()
    tickers = filter_tickers(load_etf_tickers(args.config), args.tickers)
    chunks = chunk_tickers(tickers, args.chunk_size, args.max_chunks)

    print(json.dumps([[_serialize_ticker(ticker) for ticker in chunk] for chunk in chunks]))


if __name__ == "__main__":
    main()
