"""Builds and publishes the searchable ticker catalog each ingestion
pipeline (`equicast-fx`/`equicast-stock`/`equicast-etf`/`equicast-benchmark`/
`equicast-future`) uploads after a run — the write side of the
`catalog/<asset_class>.parquet`
contract `MarketDataClient.get_catalog`/`.search` (client.py) read from.
Parquet rather than JSON, same format/tooling (`pyarrow`) as every other
file this project publishes (`profile.parquet`/`metrics.parquet`/...) —
chosen over JSON's per-row repeated field names for when the ticker
universe grows well past today's handful per asset class, even though
`search()` still reads a catalog in full on every call rather than doing a
column-pruned read.

Deliberately asset-class-agnostic and package-agnostic: every one of the
five pipelines writes its profile.parquet files to the exact same
`<asset_class>=<TICKER>/profile.parquet` local layout (see e.g.
`equicast_stock.writer.write_profile_parquet`), so `build_catalog_rows`
only needs a local directory and an `asset_class` string — no
per-pipeline config parsing (`StockTicker`/`FxPair`/...) — which is what
lets one shared CLI (`equicast-core-build-catalog`) serve every ingestion
workflow instead of one near-identical script per pipeline.

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
import logging
from pathlib import Path
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import BufferReader

logger = logging.getLogger(__name__)

#: Explicit schema for the catalog table — fixed rather than inferred from
#: `rows` so an empty ticker list (nothing published yet, or a config with
#: no tickers) still produces a valid, readable Parquet file instead of
#: pyarrow guessing column types from zero rows, and so every row (stock/
#: etf/fx alike) round-trips through the same columns regardless of which
#: fields that asset class's profile actually populates.
CATALOG_SCHEMA = pa.schema(
    [
        pa.field("ticker", pa.string()),
        pa.field("name", pa.string()),
        pa.field("type", pa.string()),
        pa.field("current_price", pa.float64()),
        pa.field("currency", pa.string()),
        pa.field("website", pa.string()),
        pa.field("market_cap", pa.float64()),
        pa.field("exchange", pa.string()),
        pa.field("region", pa.string()),
        pa.field("sector", pa.string()),
        pa.field("industry", pa.string()),
        pa.field("isin", pa.string()),
        pa.field("tax_domicile", pa.string()),
        pa.field("last_updated", pa.string()),
    ]
)


def catalog_key(asset_class: str) -> str:
    return f"catalog/{asset_class.lower()}.parquet"


def build_catalog_rows(output_dir: Path, asset_class: str) -> list[dict[str, Any]]:
    """Return one row per `<asset_class>=<TICKER>/profile.parquet` found
    under `output_dir` — exactly what a search result needs: `ticker`
    (from the directory name, not the profile itself, so this works
    uniformly across stock/etf/benchmark/future profiles carrying a
    `ticker`-like field under different names and fx profiles which have
    none — see equicast_fx.writer), `name` (`name` for stock/etf/benchmark/
    future, `description` for fx — same "no literal name field" reason),
    `type` (`asset_class`), `current_price` (`day_close`, the same field
    every pipeline's profile() method already computes), `currency`
    (`currency` for stock/etf/benchmark/future; an fx pair has no such
    field — its own `current_price` is the exchange rate quoted *in*
    `to_currency`, so that's what a display of it should be formatted as),
    `website` (`None` for fx/benchmark/future profiles, which carry no such
    field — a currency pair, an index, or a futures contract has no issuer
    site to link/show a favicon for), `market_cap` — a stock's real
    `market_cap`, an etf's `total_assets` (fund AUM, the closest comparable
    "size" figure a fund has — etf profiles carry no market cap of their
    own), or `None` for fx/benchmark/future, none of which has a size
    concept at all — `exchange` (stock/etf/benchmark/future's own
    `exchange`, yfinance's raw code, e.g. "NMS"/"PCX"/"SNP"/"CMX", not a
    bare "NASDAQ"/"NYSE" string; `None` for fx, which isn't traded on one),
    `region` (stock/etf/benchmark's own `region`, yfinance's short country
    code, e.g. "us"/"gb"; `None` for fx, which isn't domiciled anywhere, and
    usually `None` for future too — yfinance rarely populates a futures
    contract's region), and `sector`/`industry` (a stock's own
    `sector`/`industry` fields; an etf profile always sets both to the
    literal "Exchange Traded Fund", since yfinance never populates either
    for a fund — `category` is its closest equivalent but isn't surfaced
    here — same reasoning as "Mutual Fund" for a mutual-fund profile, once
    that asset class exists; always `None` for benchmark/future, which
    yfinance never populates these for either, and for fx, which has no
    such concept at all), and `last_updated` (every asset class's profile
    carries this field already, stamped by its own ingestion pipeline —
    see equicast_stock/etf/fx/benchmark/future's writers/clients — so it
    round-trips here unchanged), `isin` (stock/etf profiles only; `None`
    for fx/benchmark/future, which don't carry one), and `tax_domicile`
    (GitHub issue #94 — stock/etf profiles only, either that ticker's
    config override or derived from its `isin`; see
    `equicast_stock.cli._derive_tax_domicile`).

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
                "currency": profile.get("currency") or profile.get("to_currency"),
                "website": profile.get("website"),
                "market_cap": profile.get("market_cap") or profile.get("total_assets"),
                "exchange": profile.get("exchange"),
                "region": profile.get("region"),
                "sector": profile.get("sector"),
                "industry": profile.get("industry"),
                "isin": profile.get("isin"),
                "tax_domicile": profile.get("tax_domicile"),
                "last_updated": profile.get("last_updated"),
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
    """Upload `rows` as `catalog/<asset_class>.parquet`, replacing whatever
    catalog this asset class previously had — a full rebuild each run
    (not a merge), since `rows` already reflects that pipeline's complete,
    just-refreshed ticker list rather than a partial update. Written
    against `CATALOG_SCHEMA` rather than a schema inferred from `rows`, so
    an empty ticker list still produces a valid, readable file."""
    s3 = s3_client or boto3.client("s3", region_name=region_name)
    table = pa.Table.from_pylist(rows, schema=CATALOG_SCHEMA)
    buffer = pa.BufferOutputStream()
    pq.write_table(table, buffer)
    s3.put_object(
        Bucket=bucket,
        Key=catalog_key(asset_class),
        Body=buffer.getvalue().to_pybytes(),
        ContentType="application/octet-stream",
    )


def download_catalog_rows(
    bucket: str,
    asset_class: str,
    s3_client: Any = None,
    region_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return every row of this asset class's existing `catalog/*.parquet`,
    or an empty list if it hasn't been published yet. Used to merge a
    targeted (subset-of-tickers) run's freshly-fetched rows into the
    existing catalog instead of replacing it outright — see
    `merge_catalog_rows`."""
    s3 = s3_client or boto3.client("s3", region_name=region_name)
    try:
        response = s3.get_object(Bucket=bucket, Key=catalog_key(asset_class))
    except s3.exceptions.NoSuchKey:
        return []
    return pq.read_table(BufferReader(response["Body"].read())).to_pylist()


def merge_catalog_rows(
    existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Replace whichever `existing_rows` share a ticker with `new_rows`,
    keep every other existing row untouched, and add any ticker `new_rows`
    introduces that wasn't in the catalog before. Sorted by ticker, matching
    `build_catalog_rows`' own ordering.

    Used only for a targeted (--tickers) ingestion run, whose `output_dir`
    holds just the subset of tickers that run fetched — a full
    `upload_catalog` replace from that subset would drop every ticker the
    run didn't touch. A full (untargeted) run keeps using the plain
    replace, since its rows already are the complete, freshly-fetched
    ticker list."""
    merged = {row["ticker"]: row for row in existing_rows}
    merged.update({row["ticker"]: row for row in new_rows})
    return [merged[ticker] for ticker in sorted(merged)]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and upload the catalog/<asset_class>.parquet search catalog from a "
        "local directory of already-fetched <asset_class>=<TICKER>/profile.parquet files."
    )
    parser.add_argument(
        "--asset-class",
        required=True,
        choices=["fx", "stock", "etf", "benchmark", "future"],
        help="Asset class.",
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
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge these rows into the existing catalog instead of replacing it outright — "
        "use for a targeted (subset-of-tickers) run, whose --output-dir doesn't reflect the "
        "full ticker list.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()

    fetched_rows = build_catalog_rows(args.output_dir, args.asset_class)
    if args.merge:
        existing_rows = download_catalog_rows(
            args.bucket, args.asset_class, region_name=args.region
        )
        rows = merge_catalog_rows(existing_rows, fetched_rows)
        logger.info(
            "Merged %d freshly-fetched row(s) into the existing catalog for asset_class=%s "
            "(%d row(s) total)",
            len(fetched_rows),
            args.asset_class,
            len(rows),
        )
    else:
        rows = fetched_rows
        logger.info("Built %d catalog row(s) for asset_class=%s", len(rows), args.asset_class)

    # A real run - merge or full-replace - always has at least one row to
    # publish; the only way `rows` ends up empty is upstream breakage (e.g.
    # build_catalog_rows finding no profile.parquet files under
    # --output-dir at all, as happened when a CI artifact path mismatch
    # left it looking one directory too shallow). Refusing to publish
    # turns that into a loud pipeline failure instead of a silently empty
    # catalog/<asset_class>.parquet that makes search return nothing for
    # every query with no error anywhere.
    if not rows:
        raise SystemExit(
            f"Refusing to publish an empty catalog for asset_class={args.asset_class} - "
            f"build_catalog_rows found no profile.parquet files under {args.output_dir}. "
            "Check the ingestion job's artifact upload/download paths."
        )

    upload_catalog(args.bucket, args.asset_class, rows, region_name=args.region)


if __name__ == "__main__":
    main()
