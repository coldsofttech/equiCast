"""Write extracted stock data as Parquet, partitioned by ticker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

#: Explicit schema for events.parquet, rather than letting pyarrow infer one
#: per year-file from whatever rows land in it: a ticker-year with only
#: earnings (say) leaves rating/split-only columns (firm, ratio, ...)
#: entirely null in that slice, and pyarrow would otherwise infer a bare
#: `null` type there. Pinning real types keeps every year's file schema-
#: compatible with every other (important for tools that expect a uniform
#: schema across a partitioned dataset, e.g. Athena/Glue over
#: `stock=*/year=*/events.parquet`), rather than one year's file disagreeing
#: on a column's type with the next.
#:
#: This does NOT make an all-null string column round-trip as `None` via
#: plain `pd.read_parquet()`, though - pyarrow's default numpy-backed
#: `to_pandas()` conversion collapses any fully-null column to a float64
#: `NaN` array regardless of its declared type, a general pyarrow/pandas
#: interop quirk unrelated to schema pinning. `pd.read_parquet(path,
#: dtype_backend="pyarrow")` reads it back as the correct type with real
#: `None`/`pd.NA` if that distinction matters to a consumer.
_EVENTS_SCHEMA = pa.schema(
    [
        ("ticker", pa.string()),
        ("event_type", pa.string()),
        ("date", pa.string()),
        ("eps_estimate", pa.float64()),
        ("reported_eps", pa.float64()),
        ("surprise_pct", pa.float64()),
        ("firm", pa.string()),
        ("from_grade", pa.string()),
        ("to_grade", pa.string()),
        ("action", pa.string()),
        ("ratio", pa.float64()),
        ("last_updated", pa.string()),
        ("source", pa.string()),
    ]
)


def write_profile_parquet(profile: dict[str, Any], output_dir: Path) -> Path:
    """Write `profile` to `<output_dir>/stock=<TICKER>/profile.parquet`.

    `ceos` is JSON-encoded to a plain string column here rather than written
    as a native list<struct> column: pandas/pyarrow round-trip that type
    fine, but common Parquet viewers (browser-based tools, editor
    extensions) are JS-based and just call `toString()` on the nested
    objects, rendering "[object Object]" instead of the actual data. A JSON
    string reads correctly in any viewer; consumers `json.loads()` it back.
    """
    record = {**profile, "ceos": json.dumps(profile["ceos"], ensure_ascii=False)}

    directory = output_dir / f"stock={profile['ticker']}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.parquet"
    pd.DataFrame([record]).to_parquet(path, index=False)
    return path


def write_metrics_parquet(metrics: dict[str, Any], ticker: str, output_dir: Path) -> Path:
    """Write `metrics` to `<output_dir>/stock=<TICKER>/metrics.parquet`.

    Unlike profile()/prices(), MetricsClient is generic (keyed by a plain
    yfinance symbol, not a ticker), so the ticker identification is added
    here rather than already being present in `metrics`.
    """
    record = {"ticker": ticker, **metrics}
    directory = output_dir / f"stock={ticker}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "metrics.parquet"
    pd.DataFrame([record]).to_parquet(path, index=False)
    return path


def write_price_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to one `<output_dir>/stock=<TICKER>/year=<YYYY>/price.parquet` per year."""
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    years = df["date"].str[:4]

    written = []
    for year, year_df in df.groupby(years):
        directory = output_dir / f"stock={ticker}" / f"year={year}"
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "price.parquet"
        year_df.to_parquet(path, index=False)
        written.append(path)
    return written


def write_dividend_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to one `<output_dir>/stock=<TICKER>/year=<YYYY>/dividend.parquet`
    per year."""
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    years = df["ex_dividend_date"].str[:4]

    written = []
    for year, year_df in df.groupby(years):
        directory = output_dir / f"stock={ticker}" / f"year={year}"
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "dividend.parquet"
        year_df.to_parquet(path, index=False)
        written.append(path)
    return written


def write_events_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to one `<output_dir>/stock=<TICKER>/year=<YYYY>/events.parquet`
    per year.

    Unlike price/dividend, `records` mixes three distinct event types
    (earnings, rating changes, splits) tagged by an `event_type` column, so
    one year's file can hold everything that happened to the ticker that
    year rather than splitting across separate files per type. Written with
    an explicit schema (`_EVENTS_SCHEMA`), not `DataFrame.to_parquet`'s
    default type inference - see `_EVENTS_SCHEMA`'s comment for why.
    """
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    years = df["date"].str[:4]

    written = []
    for year, year_df in df.groupby(years):
        directory = output_dir / f"stock={ticker}" / f"year={year}"
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "events.parquet"
        table = pa.Table.from_pandas(year_df, schema=_EVENTS_SCHEMA, preserve_index=False)
        pq.write_table(table, path)
        written.append(path)
    return written
