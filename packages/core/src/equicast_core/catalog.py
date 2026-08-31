"""Builds and publishes the searchable ticker catalog each ingestion
pipeline (`equicast-fx`/`equicast-stock`/`equicast-etf`) uploads after a
run — the write side of the `catalog/<asset_class>.json` contract
`MarketDataClient.get_catalog`/`.search` (client.py) read from.

Deliberately asset-class-agnostic and package-agnostic: every one of the
three pipelines writes its profile.parquet files to the exact same
`<asset_class>=<TICKER>/profile.parquet` local layout (see e.g.
`equicast_stock.writer.write_profile_parquet`), so `build_catalog_rows`
only needs a local directory and an `asset_class` string — no
per-pipeline config parsing (`StockTicker`/`FxPair`/...) — which is what
lets one shared CLI (`equicast-core-build-catalog`) serve all three
ingestion workflows instead of three near-identical scripts.

Each ingestion pipeline's own container only ever processes one matrix-
chunked subset of its full ticker list (GitHub Actions caps a single
workflow's matrix at 256 legs — see `equicast_stock.plan`), so this can't
run inside that container: it has to run once, after every chunk's local
`output/` directory has been merged back together (via upload/download-
artifact in the ingestion workflow), against the complete merged tree —
otherwise the catalog it builds would only cover whichever chunk happened
to run last.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import boto3
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


def catalog_key(asset_class: str) -> str:
    return f"catalog/{asset_class.lower()}.json"


def build_catalog_rows(output_dir: Path, asset_class: str) -> list[dict[str, Any]]:
    """Return one row per `<asset_class>=<TICKER>/profile.parquet` found
    under `output_dir` — exactly what a search result needs: `ticker`
    (from the directory name, not the profile itself, so this works
    uniformly across stock/etf profiles carrying a `ticker` field and fx
    profiles which don't — see equicast_fx.writer), `name` (`name` for
    stock/etf, `description` for fx — same "no literal name field" reason),
    `type` (`asset_class`), and `current_price` (`day_close`, the same
    field all three pipelines' profile() methods already compute).

    Sorted by ticker for a deterministic catalog file (stable diffs run to
    run, and no reliance on filesystem iteration order)."""
    prefix = f"{asset_class.lower()}="
    rows = []
    for profile_path in sorted(output_dir.glob(f"{prefix}*/profile.parquet")):
        ticker = profile_path.parent.name[len(prefix) :]
        profile = pq.read_table(profile_path).to_pylist()[0]
        rows.append(
            {
                "ticker": ticker,
                "name": profile.get("name") or profile.get("description"),
                "type": asset_class.lower(),
                "current_price": profile.get("day_close"),
            }
        )
    return rows


def upload_catalog(
    bucket: str,
    asset_class: str,
    rows: list[dict[str, Any]],
    s3_client: Any = None,
    region_name: str | None = None,
) -> None:
    """Upload `rows` as `catalog/<asset_class>.json`, replacing whatever
    catalog this asset class previously had — a full rebuild each run
    (not a merge), since `rows` already reflects that pipeline's complete,
    just-refreshed ticker list rather than a partial update."""
    s3 = s3_client or boto3.client("s3", region_name=region_name)
    s3.put_object(
        Bucket=bucket,
        Key=catalog_key(asset_class),
        Body=json.dumps({"tickers": rows}).encode("utf-8"),
        ContentType="application/json",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and upload the catalog/<asset_class>.json search catalog from a "
        "local directory of already-fetched <asset_class>=<TICKER>/profile.parquet files."
    )
    parser.add_argument(
        "--asset-class", required=True, choices=["fx", "stock", "etf"], help="Asset class."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory containing every <asset_class>=<TICKER>/profile.parquet for this run "
        "(e.g. every ingestion matrix chunk's output, merged into one tree).",
    )
    parser.add_argument("--bucket", required=True, help="Market-data S3 bucket to upload to.")
    parser.add_argument("--region", default=None, help="AWS region (defaults to boto3's own).")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()

    rows = build_catalog_rows(args.output_dir, args.asset_class)
    logger.info("Built %d catalog row(s) for asset_class=%s", len(rows), args.asset_class)
    upload_catalog(args.bucket, args.asset_class, rows, region_name=args.region)


if __name__ == "__main__":
    main()
