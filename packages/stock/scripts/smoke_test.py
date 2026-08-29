"""Smoke-test equicast-stock against live yfinance data.

Not part of the automated pytest suite (it hits the real Yahoo Finance API,
so it doesn't belong in CI) — run manually to sanity-check
StockClient.profile(), .prices(), and the Parquet writers, end to end.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --tickers AAPL,MSFT
    uv run python scripts/smoke_test.py --format parquet --out ./smoke_output
    uv run python scripts/smoke_test.py --full-load
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from equicast_stock.client import StockClient
from equicast_stock.config import StockTicker, load_stock_tickers
from equicast_stock.writer import write_price_parquet, write_profile_parquet

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "stocks.yaml"


def _parse_tickers(raw: str) -> list[StockTicker]:
    tickers = []
    for item in raw.split(","):
        ticker = item.strip()
        if not ticker:
            raise ValueError(f"Invalid ticker '{item}'")
        tickers.append(StockTicker(ticker=ticker.upper()))
    return tickers


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test equicast-stock (profile + prices) against live yfinance data."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Stock tickers YAML to test (default: {DEFAULT_CONFIG.name}, "
        "the real pipeline config).",
    )
    parser.add_argument(
        "--tickers",
        help="Override --config: comma-separated tickers (e.g. AAPL,MSFT).",
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
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Fetch each ticker's entire yfinance history for prices, instead of just "
        "the current year.",
    )
    return parser


def _summarize_prices(records: list[dict]) -> dict:
    if not records:
        return {"rows": 0}
    return {
        "rows": len(records),
        "date_range": [records[0]["date"], records[-1]["date"]],
        "first_row": records[0],
        "last_row": records[-1],
    }


def run_ticker(ticker: StockTicker, output_format: str, output_dir: Path, full_load: bool) -> None:
    client = StockClient(ticker.ticker)
    print(f"\n=== {ticker.key} ===")

    profile = client.profile()
    prices = client.prices(full_load=full_load)

    if output_format == "json":
        print(f"\n--- {ticker.key} profile ---")
        print(json.dumps(profile, indent=2, default=str))
        print(f"\n--- {ticker.key} prices (summary; full_load={full_load}) ---")
        print(json.dumps(_summarize_prices(prices), indent=2, default=str))
    else:
        profile_path = write_profile_parquet(profile, output_dir)
        price_paths = write_price_parquet(prices, output_dir)
        print(f"  wrote {profile_path}")
        for path in price_paths:
            print(f"  wrote {path}")


def main() -> None:
    args = build_arg_parser().parse_args()

    try:
        tickers = _parse_tickers(args.tickers) if args.tickers else load_stock_tickers(args.config)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for ticker in tickers:
        run_ticker(ticker, args.format, args.out, args.full_load)


if __name__ == "__main__":
    main()
