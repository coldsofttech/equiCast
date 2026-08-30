"""Class-based client for reading equicast's S3 market-data layout.

Generic across consumers (Django backend, Lambda, scripts) and across asset
classes (`fx`/`stock`/`etf`) — it only knows the S3 key layout the ingestion
pipelines write to (`<asset_class>=<symbol>/profile.parquet`,
`<asset_class>=<symbol>/year=<YYYY>/price.parquet`), nothing about Django or
any particular caller.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import boto3
import pyarrow.parquet as pq
from pyarrow import BufferReader


class MarketDataClient:
    """Reads profile/price Parquet objects from one S3 bucket."""

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
        ticker/pair has no `profile.parquet` in the bucket."""
        key = f"{asset_class.lower()}={symbol.upper()}/profile.parquet"
        rows = self._read_parquet(key)
        return rows[0] if rows else None

    def get_prices(self, asset_class: str, symbol: str) -> list[dict[str, Any]]:
        """Return this calendar year's daily OHLC rows for `symbol`, or `[]`
        if none exist yet (not-yet-configured ticker, or no trading days so
        far this year)."""
        year = datetime.now(UTC).year
        key = f"{asset_class.lower()}={symbol.upper()}/year={year}/price.parquet"
        rows = self._read_parquet(key)
        return rows or []
