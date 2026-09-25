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

Deliberately asset-class-agnostic and package-agnostic for stock/etf/
benchmark/future: every one of those pipelines writes its profile.parquet
files to the exact same `<asset_class>=<TICKER>/profile.parquet` local
layout (see e.g. `equicast_stock.writer.write_profile_parquet`), so
`build_catalog_rows` only needs a local directory and an `asset_class`
string for them — no per-pipeline config parsing (`StockTicker`/`FxPair`/
...) — which is what lets one shared CLI (`equicast-core-build-catalog`)
serve every ingestion workflow instead of one near-identical script per
pipeline. `fx` is the first asset class merged under equicast-support#232
and gets its own row-building/schema path (`_build_fx_catalog_rows`/
`FX_CATALOG_SCHEMA`) instead, since a currency pair has none of
website/market_cap/sector/industry/isin/tax_domicile/exchange/region's
concepts at all (always null in the generic shape) — the others keep the
original generic path until they get the same treatment.

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
#: etf alike) round-trips through the same columns regardless of which
#: fields that asset class's profile actually populates.
#:
#: `fx` no longer uses this schema — see `FX_CATALOG_SCHEMA`.
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
        pa.field("cagr_1y", pa.float64()),
        pa.field("change_1w_pct", pa.float64()),
        pa.field("change_1m_pct", pa.float64()),
        pa.field("last_updated", pa.string()),
    ]
)

#: equicast-support#232 (fx slice): fx's own catalog schema, replacing its
#: separate `profile.parquet`/`metrics.parquet` — every field either file
#: actually populated for a currency pair, minus `source` (both files'
#: copy is a constant provenance tag - "yfinance"/"equicast" - dropped the
#: same way `equicast_core.client._without_source` already drops it from
#: every API response; never stored at all now, for fx). Does *not* include
#: `website`/`market_cap`/`sector`/`industry`/`isin`/`tax_domicile`/
#: `exchange`/`region` - fx has no such concepts (a currency pair isn't
#: traded on an exchange, domiciled anywhere, or issued by a company), and
#: those 8 fields have always come back `None` for every fx row in the
#: generic `CATALOG_SCHEMA` (see the old `build_catalog_rows`'s own
#: docstring). Every consumer of a catalog row (`MarketDataClient.search`/
#: `.enrich_holdings`) already reads fields via `dict.get(...)`, never
#: direct indexing, so a fx row simply not carrying these keys is
#: indistinguishable from today's always-`None` values to every caller.
FX_CATALOG_SCHEMA = pa.schema(
    [
        pa.field("ticker", pa.string()),
        pa.field("from_currency", pa.string()),
        pa.field("to_currency", pa.string()),
        pa.field("name", pa.string()),
        pa.field("type", pa.string()),
        pa.field("current_price", pa.float64()),
        pa.field("currency", pa.string()),
        pa.field("day_open", pa.float64()),
        pa.field("day_high", pa.float64()),
        pa.field("day_low", pa.float64()),
        pa.field("day_close", pa.float64()),
        pa.field("year_open", pa.float64()),
        pa.field("year_high", pa.float64()),
        pa.field("year_low", pa.float64()),
        pa.field("year_close", pa.float64()),
        pa.field("volatility", pa.float64()),
        pa.field("sharpe_ratio", pa.float64()),
        pa.field("max_drawdown", pa.float64()),
        pa.field("cagr_1y", pa.float64()),
        pa.field("cagr_2y", pa.float64()),
        pa.field("cagr_3y", pa.float64()),
        pa.field("cagr_5y", pa.float64()),
        pa.field("cagr_10y", pa.float64()),
        pa.field("change_1w_pct", pa.float64()),
        pa.field("change_1m_pct", pa.float64()),
        pa.field("last_updated", pa.string()),
    ]
)

#: Per-asset-class schema override — checked by `_schema_for` before
#: falling back to the generic `CATALOG_SCHEMA`. Only `fx` diverges so far
#: (equicast-support#232); stock/etf/benchmark/future stay on the generic
#: shape until they get the same treatment.
CATALOG_SCHEMAS: dict[str, pa.Schema] = {"fx": FX_CATALOG_SCHEMA}


def _schema_for(asset_class: str) -> pa.Schema:
    return CATALOG_SCHEMAS.get(asset_class.lower(), CATALOG_SCHEMA)


def catalog_key(asset_class: str) -> str:
    return f"catalog/{asset_class.lower()}.parquet"


def _build_fx_catalog_rows(output_dir: Path) -> list[dict[str, Any]]:
    """FX counterpart of the generic row-building below (equicast-support#232)
    — one row per `fx=<PAIR>/profile.parquet` found under `output_dir`,
    folding in that pair's sibling `metrics.parquet` the same way the
    generic path does. Unlike the generic path, this carries every field
    profile/metrics actually populate for a pair (`from_currency`/
    `to_currency`, the full day/year OHLC range, and every risk/performance
    metric — not just `cagr_1y`/`change_1w_pct`/`change_1m_pct`) rather than
    a fixed cross-asset-class subset, since fx no longer publishes its own
    `profile.parquet`/`metrics.parquet` to S3 — this catalog row is now the
    only place that data lives (see `equicast_core.client.MarketDataClient.
    get_profile`/`get_metrics`, which reconstruct their API-facing shape
    from it for `asset_class="fx"`).

    `metrics` defaults to `{}` for a pair with no sibling `metrics.parquet`
    yet (same as the generic path), so every metrics field comes back
    `None` rather than raising."""
    rows = []
    for profile_path in sorted(output_dir.glob("fx=*/profile.parquet")):
        ticker = profile_path.parent.name[len("fx=") :]
        profile = pq.read_table(profile_path).to_pylist()[0]

        metrics_path = profile_path.parent / "metrics.parquet"
        metrics = pq.read_table(metrics_path).to_pylist()[0] if metrics_path.exists() else {}

        rows.append(
            {
                "ticker": ticker,
                "from_currency": profile.get("from_currency"),
                "to_currency": profile.get("to_currency"),
                "name": profile.get("description"),
                "type": "fx",
                "current_price": profile.get("day_close"),
                "currency": profile.get("to_currency"),
                "day_open": profile.get("day_open"),
                "day_high": profile.get("day_high"),
                "day_low": profile.get("day_low"),
                "day_close": profile.get("day_close"),
                "year_open": profile.get("year_open"),
                "year_high": profile.get("year_high"),
                "year_low": profile.get("year_low"),
                "year_close": profile.get("year_close"),
                "volatility": metrics.get("volatility"),
                "sharpe_ratio": metrics.get("sharpe_ratio"),
                "max_drawdown": metrics.get("max_drawdown"),
                "cagr_1y": metrics.get("cagr_1y"),
                "cagr_2y": metrics.get("cagr_2y"),
                "cagr_3y": metrics.get("cagr_3y"),
                "cagr_5y": metrics.get("cagr_5y"),
                "cagr_10y": metrics.get("cagr_10y"),
                "change_1w_pct": metrics.get("change_1w_pct"),
                "change_1m_pct": metrics.get("change_1m_pct"),
                "last_updated": profile.get("last_updated"),
            }
        )
    return rows


def build_catalog_rows(output_dir: Path, asset_class: str) -> list[dict[str, Any]]:
    """Return one row per `<asset_class>=<TICKER>/profile.parquet` found
    under `output_dir` — exactly what a search result needs: `ticker`
    (from the directory name, not the profile itself, so this works
    uniformly across stock/etf/benchmark/future profiles carrying a
    `ticker`-like field under different names — see equicast_fx.writer for
    why fx itself no longer goes through this function at all),
    `name` (`name` for stock/etf/benchmark/future), `type` (`asset_class`),
    `current_price` (`day_close`, the same field every pipeline's profile()
    method already computes), `currency` (`currency` for stock/etf/
    benchmark/future), `website` (`None` for benchmark/future profiles,
    which carry no such field — an index or a futures contract has no
    issuer site to link/show a favicon for), `market_cap` — a stock's real
    `market_cap`, an etf's `total_assets` (fund AUM, the closest comparable
    "size" figure a fund has — etf profiles carry no market cap of their
    own), or `None` for benchmark/future, neither of which has a size
    concept at all — `exchange` (stock/etf/benchmark/future's own
    `exchange`, yfinance's raw code, e.g. "NMS"/"PCX"/"SNP"/"CMX"),
    `region` (stock/etf/benchmark's own `region`, yfinance's short country
    code, e.g. "us"/"gb"; usually `None` for future too — yfinance rarely
    populates a futures contract's region), and `sector`/`industry` (a
    stock's own `sector`/`industry` fields; an etf profile always sets both
    to the literal "Exchange Traded Fund", since yfinance never populates
    either for a fund — `category` is its closest equivalent but isn't
    surfaced here — same reasoning as "Mutual Fund" for a mutual-fund
    profile, once that asset class exists; always `None` for benchmark/
    future, which yfinance never populates these for either), and
    `last_updated` (every asset class's profile carries this field already,
    stamped by its own ingestion pipeline — see equicast_stock/etf/
    benchmark/future's writers/clients — so it round-trips here unchanged),
    `isin` (stock/etf profiles only; `None` for benchmark/future, which
    don't carry one), and `tax_domicile` (GitHub issue #94 — stock/etf
    profiles only, either that ticker's config override or derived from its
    `isin`; see `equicast_stock.cli._derive_tax_domicile`).

    Also folds in `cagr_1y`/`change_1w_pct`/`change_1m_pct` from that same
    ticker's sibling `metrics.parquet` (see `equicast_metrics.MetricsClient.
    metrics()`) when present alongside its `profile.parquet` — the same
    ingestion run already writes both, and the workflow that calls this
    (each ingestion pipeline's own "build-catalog" job) already downloads
    both as one artifact, so this is a local read, never a new S3 round
    trip. All three come back `None` for a ticker with no `metrics.parquet`
    yet (an ingestion run predating this feature, or one that only
    refreshed profiles) rather than raising — one asset class's catalog
    build shouldn't fail because one ticker's metrics happened to lag.

    Sorted by ticker for a deterministic catalog file (stable diffs run to
    run, and no reliance on filesystem iteration order).

    `asset_class="fx"` is handled entirely by `_build_fx_catalog_rows`
    instead (equicast-support#232) — a currency pair has none of this
    function's website/market_cap/exchange/region/sector/industry/isin/
    tax_domicile concepts, so fx gets its own row shape/schema
    (`FX_CATALOG_SCHEMA`) rather than a row full of always-`None` columns.
    """
    if asset_class.lower() == "fx":
        return _build_fx_catalog_rows(output_dir)

    prefix = f"{asset_class.lower()}="
    rows = []
    for profile_path in sorted(output_dir.glob(f"{prefix}*/profile.parquet")):
        ticker = profile_path.parent.name[len(prefix) :]
        profile = pq.read_table(profile_path).to_pylist()[0]

        metrics_path = profile_path.parent / "metrics.parquet"
        metrics = pq.read_table(metrics_path).to_pylist()[0] if metrics_path.exists() else {}

        rows.append(
            {
                "ticker": ticker,
                "name": profile.get("name"),
                "type": asset_class.lower(),
                "current_price": profile.get("day_close"),
                "currency": profile.get("currency"),
                "website": profile.get("website"),
                "market_cap": profile.get("market_cap") or profile.get("total_assets"),
                "exchange": profile.get("exchange"),
                "region": profile.get("region"),
                "sector": profile.get("sector"),
                "industry": profile.get("industry"),
                "isin": profile.get("isin"),
                "tax_domicile": profile.get("tax_domicile"),
                "cagr_1y": metrics.get("cagr_1y"),
                "change_1w_pct": metrics.get("change_1w_pct"),
                "change_1m_pct": metrics.get("change_1m_pct"),
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
    against that asset class's own schema (`_schema_for` — `fx` uses
    `FX_CATALOG_SCHEMA`, everything else the generic `CATALOG_SCHEMA`)
    rather than a schema inferred from `rows`, so an empty ticker list
    still produces a valid, readable file."""
    s3 = s3_client or boto3.client("s3", region_name=region_name)
    table = pa.Table.from_pylist(rows, schema=_schema_for(asset_class))
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
