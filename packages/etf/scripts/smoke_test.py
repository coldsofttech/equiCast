"""Smoke-test equicast-etf against live yfinance data.

Not part of the automated pytest suite (it hits the real Yahoo Finance API,
so it doesn't belong in CI) — run manually to sanity-check
ETFClient.profile() and the Parquet writer, end to end.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --tickers VOO,QQQ
    uv run python scripts/smoke_test.py --format parquet --out ./smoke_output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from equicast_etf.client import ETFClient
from equicast_etf.config import ETFTicker, load_etf_tickers
from equicast_etf.writer import write_profile_parquet

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "etfs.yaml"


def _parse_tickers(raw: str) -> list[ETFTicker]:
    tickers = []
    for item in raw.split(","):
        ticker = item.strip()
        if not ticker:
            raise ValueError(f"Invalid ticker '{item}'")
        tickers.append(ETFTicker(ticker=ticker.upper()))
    return tickers


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test equicast-etf (profile) against live yfinance data."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"ETF tickers YAML to test (default: {DEFAULT_CONFIG.name}, "
        "the real pipeline config).",
    )
    parser.add_argument(
        "--tickers",
        help="Override --config: comma-separated tickers (e.g. VOO,QQQ).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "parquet"],
        default="json",
        help="json prints results to stdout; parquet writes real files via the writer "
        "(default: json).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("./smoke_output"),
        help="Output directory when --format parquet (default: ./smoke_output).",
    )
    return parser


def run_ticker(ticker: ETFTicker, output_format: str, output_dir: Path) -> None:
    client = ETFClient(ticker.ticker)
    print(f"\n=== {ticker.key} ===")

    profile = client.profile()

    if output_format == "json":
        print(f"\n--- {ticker.key} profile ---")
        print(json.dumps(profile, indent=2, default=str))
    else:
        profile_path = write_profile_parquet(profile, output_dir)
        print(f"  wrote {profile_path}")


def main() -> None:
    args = build_arg_parser().parse_args()

    try:
        tickers = _parse_tickers(args.tickers) if args.tickers else load_etf_tickers(args.config)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for ticker in tickers:
        run_ticker(ticker, args.format, args.out)


if __name__ == "__main__":
    main()
