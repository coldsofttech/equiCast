"""Smoke-test equicast-fx against live yfinance data.

Not part of the automated pytest suite (it hits the real Yahoo Finance API,
so it doesn't belong in CI) — run manually to sanity-check FXClient.profile(),
.prices(), MetricsClient.metrics(), and the Parquet writers, end to end.

Usage:
    uv run python scripts/smoke_test.py
    uv run python scripts/smoke_test.py --pairs GBP:USD,EUR:GBP
    uv run python scripts/smoke_test.py --format parquet --out ./smoke_output
    uv run python scripts/smoke_test.py --full-load
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from equicast_fx.client import FXClient
from equicast_fx.config import FxPair, load_fx_pairs
from equicast_fx.writer import write_metrics_parquet, write_price_parquet, write_profile_parquet
from equicast_metrics import MetricsClient

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "fx_pairs.yaml"


def _parse_pairs(raw: str) -> list[FxPair]:
    pairs = []
    for item in raw.split(","):
        from_currency, sep, to_currency = item.strip().partition(":")
        if not sep or not from_currency or not to_currency:
            raise ValueError(f"Invalid pair '{item}', expected FROM:TO (e.g. GBP:USD)")
        pairs.append(FxPair(from_currency=from_currency.upper(), to_currency=to_currency.upper()))
    return pairs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke-test equicast-fx (profile + prices + metrics) against live "
        "yfinance data."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"FX pairs YAML to test (default: {DEFAULT_CONFIG.name}, the real pipeline config).",
    )
    parser.add_argument(
        "--pairs",
        help="Override --config: comma-separated FROM:TO pairs (e.g. GBP:USD,EUR:GBP).",
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
        help="Fetch each pair's entire yfinance history for prices, instead of just "
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


def run_pair(pair: FxPair, output_format: str, output_dir: Path, full_load: bool) -> None:
    client = FXClient(pair.from_currency, pair.to_currency)
    metrics_client = MetricsClient(client.symbol)
    print(f"\n=== {pair.key} ===")

    profile = client.profile()
    prices = client.prices(full_load=full_load)
    metrics = metrics_client.metrics()

    if output_format == "json":
        print(f"\n--- {pair.key} profile ---")
        print(json.dumps(profile, indent=2, default=str))
        print(f"\n--- {pair.key} prices (summary; full_load={full_load}) ---")
        print(json.dumps(_summarize_prices(prices), indent=2, default=str))
        print(f"\n--- {pair.key} metrics ---")
        print(json.dumps(metrics, indent=2, default=str))
    else:
        profile_path = write_profile_parquet(profile, output_dir)
        price_paths = write_price_parquet(prices, output_dir)
        metrics_path = write_metrics_parquet(
            metrics, pair.from_currency, pair.to_currency, output_dir
        )
        print(f"  wrote {profile_path}")
        for path in price_paths:
            print(f"  wrote {path}")
        print(f"  wrote {metrics_path}")


def main() -> None:
    args = build_arg_parser().parse_args()

    try:
        pairs = _parse_pairs(args.pairs) if args.pairs else load_fx_pairs(args.config)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    for pair in pairs:
        run_pair(pair, args.format, args.out, args.full_load)


if __name__ == "__main__":
    main()
