"""Smoke-test equicast-future against live yfinance data.

Not part of the automated pytest suite (it hits the real Yahoo Finance API,
so it doesn't belong in CI) — run manually to sanity-check
FutureClient.profile(), .prices(), MetricsClient.metrics(), and the
Parquet writers, end to end.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --futures GOLD:GC=F,SILVER:SI=F
    uv run python scripts/smoke_test.py --format parquet --out ./smoke_output
    uv run python scripts/smoke_test.py --full-load
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from equicast_future.client import FutureClient
from equicast_future.config import Future, load_futures
from equicast_future.writer import write_metrics_parquet, write_price_parquet, write_profile_parquet
from equicast_metrics import MetricsClient

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "futures.dev.yaml"


def _parse_futures(raw: str) -> list[Future]:
    futures = []
    for item in raw.split(","):
        key, sep, symbol = item.strip().partition(":")
        if not sep or not key or not symbol:
            raise ValueError(f"Invalid future '{item}', expected KEY:SYMBOL (e.g. GOLD:GC=F)")
        futures.append(Future(key=key.upper(), symbol=symbol))
    return futures


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test equicast-future (profile + prices + metrics) against live "
        "yfinance data."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Futures YAML to test (default: {DEFAULT_CONFIG.name}, the real pipeline config).",
    )
    parser.add_argument(
        "--futures",
        help="Override --config: comma-separated KEY:SYMBOL futures (e.g. GOLD:GC=F,SILVER:SI=F).",
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
        help="Fetch each future's entire yfinance history for prices, instead of just "
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


def run_future(future: Future, output_format: str, output_dir: Path, full_load: bool) -> None:
    client = FutureClient(future.key, future.symbol)
    metrics_client = MetricsClient(client.symbol)
    print(f"\n=== {future.key} ({future.symbol}) ===")

    profile = client.profile()
    prices = client.prices(full_load=full_load)
    metrics = metrics_client.metrics()

    if output_format == "json":
        print(f"\n--- {future.key} profile ---")
        print(json.dumps(profile, indent=2, default=str))
        print(f"\n--- {future.key} prices (summary; full_load={full_load}) ---")
        print(json.dumps(_summarize_prices(prices), indent=2, default=str))
        print(f"\n--- {future.key} metrics ---")
        print(json.dumps(metrics, indent=2, default=str))
    else:
        profile_path = write_profile_parquet(profile, output_dir)
        price_paths = write_price_parquet(prices, output_dir)
        metrics_path = write_metrics_parquet(metrics, future.key, output_dir)
        print(f"  wrote {profile_path}")
        for path in price_paths:
            print(f"  wrote {path}")
        print(f"  wrote {metrics_path}")


def main() -> None:
    args = build_arg_parser().parse_args()

    try:
        futures = _parse_futures(args.futures) if args.futures else load_futures(args.config)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for future in futures:
        run_future(future, args.format, args.out, args.full_load)


if __name__ == "__main__":
    main()
