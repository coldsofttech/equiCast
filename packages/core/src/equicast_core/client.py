"""Class-based client for reading equicast's S3 market-data layout.

Generic across consumers (Django backend, Lambda, scripts) and across asset
classes (`fx`/`stock`/`etf`) — it only knows the S3 key layout the ingestion
pipelines write to (`<asset_class>=<symbol>/profile.parquet`,
`<asset_class>=<symbol>/price/current.parquet` and
`<asset_class>=<symbol>/price/history.parquet`,
`catalog/<asset_class>.json` — see `equicast_core.catalog` for how the
latter is built/uploaded by each ingestion pipeline), nothing about Django
or any particular caller.
"""

from __future__ import annotations

import json
from typing import Any

import boto3
import pyarrow.parquet as pq
from pyarrow import BufferReader

from equicast_core.catalog import catalog_key

#: Every asset class `search()` scans when no `asset_classes` filter is
#: given, in a fixed order so results are grouped predictably rather than
#: interleaved by whatever order a caller happened to pass filters in.
ASSET_CLASSES = ("fx", "stock", "etf")


class MarketDataClient:
    """Reads profile/price/catalog Parquet/JSON objects from one S3
    bucket."""

    def __init__(self, bucket: str, s3_client: Any = None, region_name: str | None = None) -> None:
        self._bucket = bucket
        self._s3 = s3_client or boto3.client("s3", region_name=region_name)

    def _read_parquet(self, key: str) -> list[dict[str, Any]] | None:
        """Return every row of the Parquet object at `key`, or `None` if it
        doesn't exist. Any other S3 error propagates as-is."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=key)
        except self._s3.exceptions.NoSuchKey:
            return None
        body = response["Body"].read()
        table = pq.read_table(BufferReader(body))
        return table.to_pylist()

    def get_profile(self, asset_class: str, symbol: str) -> dict[str, Any] | None:
        """Return the single profile record for `symbol`, or `None` if this
        ticker/pair has no `profile.parquet` in the bucket.

        A stock profile's `ceos` is written as a JSON-encoded string column
        (see `equicast_stock.writer.write_profile_parquet`'s docstring —
        Parquet viewers render a native list<struct> column as
        "[object Object]", so the writer stores JSON text instead and
        documents that consumers decode it back); decoded here so every
        caller of this client gets a real list, not a raw JSON string. Only
        touched when present and still a string — etf/fx profiles have no
        `ceos` field at all, and a value that's already a list (e.g. from a
        test fixture) is left as-is rather than re-decoded.
        """
        key = f"{asset_class.lower()}={symbol.upper()}/profile.parquet"
        rows = self._read_parquet(key)
        if not rows:
            return None
        profile = rows[0]
        if isinstance(profile.get("ceos"), str):
            profile = {**profile, "ceos": json.loads(profile["ceos"])}
        return profile

    def get_prices(self, asset_class: str, symbol: str) -> list[dict[str, Any]]:
        """Return this calendar year's daily OHLC rows for `symbol`, or `[]`
        if none exist yet (not-yet-configured ticker, or no trading days so
        far this year).

        Reads `price/current.parquet` — the current year only, same as
        before this was split from a `year=<YYYY>/price.parquet` per year.
        `price/history.parquet` (every earlier year, written once by a
        `--full-load` ingestion run) isn't read here; nothing currently
        needs prior-year rows."""
        key = f"{asset_class.lower()}={symbol.upper()}/price/current.parquet"
        rows = self._read_parquet(key)
        return rows or []

    def get_catalog(self, asset_class: str) -> list[dict[str, Any]]:
        """Return every `{ticker, name, type, current_price}` row this
        asset class's ingestion pipeline last published (see
        `equicast_core.catalog`), or `[]` if no catalog has been uploaded
        yet for it."""
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=catalog_key(asset_class))
        except self._s3.exceptions.NoSuchKey:
            return []
        body = json.loads(response["Body"].read())
        return body.get("tickers", [])

    def search(self, query: str, asset_classes: list[str] | None = None) -> list[dict[str, Any]]:
        """Case-insensitive substring match of `query` against every
        catalog row's `ticker` and `name`, across `asset_classes` (default:
        every asset class — see `ASSET_CLASSES`). Reads each scanned asset
        class's catalog file once (via `get_catalog`) rather than the
        bucket itself — no per-ticker S3 reads here, unlike
        `get_profile`/`get_prices`.

        Results are sorted by ticker for a stable order across calls (the
        caller — e.g. the Django view — owns pagination on top of this)."""
        classes = asset_classes if asset_classes is not None else ASSET_CLASSES
        query_lower = query.lower()

        matches = []
        for asset_class in classes:
            for row in self.get_catalog(asset_class):
                ticker = row.get("ticker") or ""
                name = row.get("name") or ""
                if query_lower in ticker.lower() or query_lower in name.lower():
                    matches.append(row)
        matches.sort(key=lambda row: row["ticker"])
        return matches
