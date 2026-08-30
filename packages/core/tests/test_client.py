from datetime import UTC, datetime
from io import BytesIO

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from equicast_core.client import MarketDataClient
from moto import mock_aws

BUCKET = "equicast-market-data-test"


def _parquet_bytes(rows: list[dict]) -> bytes:
    table = pa.Table.from_pylist(rows)
    buffer = BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_get_profile_returns_the_single_row(s3_client) -> None:
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/profile.parquet",
        Body=_parquet_bytes([{"ticker": "AAPL", "name": "Apple Inc."}]),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_profile("stock", "aapl") == {"ticker": "AAPL", "name": "Apple Inc."}


def test_get_profile_returns_none_when_key_missing(s3_client) -> None:
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_profile("stock", "MISSING") is None


def test_get_prices_returns_current_year_rows(s3_client) -> None:
    year = datetime.now(UTC).year
    rows = [
        {"ticker": "VOO", "date": "2026-01-02", "close": 624.5},
        {"ticker": "VOO", "date": "2026-01-05", "close": 628.64},
    ]
    s3_client.put_object(
        Bucket=BUCKET,
        Key=f"etf=VOO/year={year}/price.parquet",
        Body=_parquet_bytes(rows),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_prices("etf", "voo") == rows


def test_get_prices_returns_empty_list_when_key_missing(s3_client) -> None:
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_prices("etf", "MISSING") == []
