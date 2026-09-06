"""Smoke-test equicast-benchmark against live yfinance data.

Not part of the automated pytest suite (it hits the real Yahoo Finance API,
so it doesn't belong in CI) — run manually to sanity-check
BenchmarkClient.profile(), .prices(), MetricsClient.metrics(), and the
Parquet writers, end to end.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --benchmarks SP500:^GSPC,DAX:^GDAXI
    uv run python scripts/smoke_test.py --format parquet --out ./smoke_output
    uv run python scripts/smoke_test.py --full-load
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from equicast_benchmark.client import BenchmarkClient
from equicast_benchmark.config import Benchmark, load_benchmarks
from equicast_benchmark.writer import (
    write_metrics_parquet,
    write_price_parquet,
    write_profile_parquet,
)
from equicast_metrics import MetricsClient

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "benchmarks.dev.yaml"


def _parse_benchmarks(raw: str) -> list[Benchmark]:
    benchmarks = []
    for item in raw.split(","):
        key, sep, symbol = item.strip().partition(":")
        if not sep or not key or not symbol:
            raise ValueError(f"Invalid benchmark '{item}', expected KEY:SYMBOL (e.g. SP500:^GSPC)")
        benchmarks.append(Benchmark(key=key.upper(), symbol=symbol))
    return benchmarks


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test equicast-benchmark (profile + prices + metrics) against live "
        "yfinance data."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Benchmarks YAML to test (default: {DEFAULT_CONFIG.name}, the real pipeline "
        "config).",
    )
    parser.add_argument(
        "--benchmarks",
        help="Override --config: comma-separated KEY:SYMBOL benchmarks "
        "(e.g. SP500:^GSPC,DAX:^GDAXI).",
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
        help="Fetch each benchmark's entire yfinance history for prices, instead of just "
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


def run_benchmark(
    benchmark: Benchmark, output_format: str, output_dir: Path, full_load: bool
) -> None:
    client = BenchmarkClient(benchmark.key, benchmark.symbol)
    metrics_client = MetricsClient(client.symbol)
    print(f"\n=== {benchmark.key} ({benchmark.symbol}) ===")

    profile = client.profile()
    prices = client.prices(full_load=full_load)
    metrics = metrics_client.metrics()

    if output_format == "json":
        print(f"\n--- {benchmark.key} profile ---")
        print(json.dumps(profile, indent=2, default=str))
        print(f"\n--- {benchmark.key} prices (summary; full_load={full_load}) ---")
        print(json.dumps(_summarize_prices(prices), indent=2, default=str))
        print(f"\n--- {benchmark.key} metrics ---")
        print(json.dumps(metrics, indent=2, default=str))
    else:
        profile_path = write_profile_parquet(profile, output_dir)
        price_paths = write_price_parquet(prices, output_dir)
        metrics_path = write_metrics_parquet(metrics, benchmark.key, output_dir)
        print(f"  wrote {profile_path}")
        for path in price_paths:
            print(f"  wrote {path}")
        print(f"  wrote {metrics_path}")


def main() -> None:
    args = build_arg_parser().parse_args()

    try:
        benchmarks = (
            _parse_benchmarks(args.benchmarks) if args.benchmarks else load_benchmarks(args.config)
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for benchmark in benchmarks:
        run_benchmark(benchmark, args.format, args.out, args.full_load)


if __name__ == "__main__":
    main()
