"""Smoke-test equicast-stock against live yfinance data.

Not part of the automated pytest suite (it hits the real Yahoo Finance API,
so it doesn't belong in CI) — run manually to sanity-check
StockClient.profile(), .prices(), DividendsClient.dividends(),
EventsClient.events(), MetricsClient.metrics()/.fundamentals(), and the
Parquet writers, end to end.

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
from datetime import UTC, datetime
from pathlib import Path

from equicast_dividends import DividendsClient, dividend_frequency
from equicast_events import EventsClient
from equicast_metrics import MetricsClient
from equicast_stock.cli import _combine_metrics
from equicast_stock.client import StockClient
from equicast_stock.config import StockTicker, load_stock_tickers
from equicast_stock.writer import (
    write_dividend_parquet,
    write_events_parquet,
    write_metrics_parquet,
    write_price_parquet,
    write_profile_parquet,
)

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "stocks.dev.yaml"


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
        description="Smoke-test equicast-stock (profile + prices + dividends + events + "
        "metrics) against live yfinance data."
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
        help="Fetch each ticker's entire yfinance history for prices/dividends/events, "
        "instead of just the current year.",
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
    dividends_client = DividendsClient(client.symbol)
    events_client = EventsClient(client.symbol)
    metrics_client = MetricsClient(client.symbol)
    print(f"\n=== {ticker.key} ===")

    prices = client.prices(full_load=full_load)
    # Always fetched in full, same as _profile_and_dividends_task does - the
    # underlying yfinance call is identical either way (full_load only
    # controls a post-fetch filter, see DividendsClient.dividends()'s
    # docstring), so dividend_frequency() gets enough history to classify
    # regardless of --full-load. dividends_to_write below still only writes
    # what a real pipeline run would.
    dividends = dividends_client.dividends(full_load=True)
    if full_load:
        dividends_to_write = dividends
    else:
        current_year = str(datetime.now(UTC).year)
        dividends_to_write = [d for d in dividends if d["ex_dividend_date"][:4] == current_year]
    events = events_client.events(full_load=full_load)
    metrics = _combine_metrics(metrics_client.metrics(), metrics_client.fundamentals())
    profile = {**client.profile(), "dividend_frequency": dividend_frequency(dividends)}

    if output_format == "json":
        print(f"\n--- {ticker.key} profile ---")
        # CodeQL flags `profile["address"]` as sensitive personal data via its
        # generic field-name heuristic; it's actually the company's public HQ
        # address from yfinance's profile data, and printing the full profile
        # is this script's entire purpose (manual QA, never used in prod).
        profile_json = json.dumps(profile, indent=2, default=str)
        print(profile_json)  # lgtm[py/clear-text-logging-sensitive-data]
        print(f"\n--- {ticker.key} prices (summary; full_load={full_load}) ---")
        print(json.dumps(_summarize_prices(prices), indent=2, default=str))
        print(f"\n--- {ticker.key} dividends (full history, always) ---")
        print(json.dumps(dividends, indent=2, default=str))
        print(f"\n--- {ticker.key} events (full_load={full_load}) ---")
        print(json.dumps(events, indent=2, default=str))
        print(f"\n--- {ticker.key} metrics ---")
        print(json.dumps(metrics, indent=2, default=str))
    else:
        profile_path = write_profile_parquet(profile, output_dir)
        price_paths = write_price_parquet(prices, output_dir)
        dividend_paths = write_dividend_parquet(dividends_to_write, output_dir)
        events_paths = write_events_parquet(events, output_dir)
        metrics_path = write_metrics_parquet(metrics, ticker.ticker, output_dir)
        print(f"  wrote {profile_path}")
        for path in price_paths:
            print(f"  wrote {path}")
        for path in dividend_paths:
            print(f"  wrote {path}")
        for path in events_paths:
            print(f"  wrote {path}")
        print(f"  wrote {metrics_path}")


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
