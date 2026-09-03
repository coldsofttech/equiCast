import json
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


def test_get_profile_decodes_a_json_encoded_ceos_string(s3_client) -> None:
    """A stock profile's `ceos` is written as a JSON string column (see
    equicast_stock.writer.write_profile_parquet's docstring) — get_profile
    must decode it back into a real list rather than leaking the raw JSON
    text through to callers."""
    ceos = [{"name": "Timothy D. Cook", "role": "CEO"}]
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/profile.parquet",
        Body=_parquet_bytes([{"ticker": "AAPL", "ceos": json.dumps(ceos)}]),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_profile("stock", "AAPL")["ceos"] == ceos


def test_get_profile_leaves_a_missing_ceos_field_untouched(s3_client) -> None:
    """etf/fx profiles have no `ceos` field at all — get_profile shouldn't
    require one."""
    s3_client.put_object(
        Bucket=BUCKET,
        Key="fx=GBPUSD/profile.parquet",
        Body=_parquet_bytes([{"ticker": "GBPUSD"}]),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_profile("fx", "GBPUSD") == {"ticker": "GBPUSD"}


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


def _put_catalog(s3_client, asset_class: str, rows: list[dict]) -> None:
    s3_client.put_object(
        Bucket=BUCKET,
        Key=f"catalog/{asset_class}.json",
        Body=json.dumps({"tickers": rows}).encode("utf-8"),
        ContentType="application/json",
    )


class TestGetCatalog:
    def test_returns_the_published_rows(self, s3_client) -> None:
        rows = [{"ticker": "AAPL", "name": "Apple Inc.", "type": "stock", "current_price": 227.5}]
        _put_catalog(s3_client, "stock", rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_catalog("stock") == rows

    def test_returns_empty_list_when_no_catalog_published_yet(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_catalog("stock") == []


class TestSearch:
    def _seed(self, s3_client) -> None:
        _put_catalog(
            s3_client,
            "stock",
            [
                {"ticker": "AAPL", "name": "Apple Inc.", "type": "stock", "current_price": 227.5},
                {"ticker": "NVDA", "name": "NVIDIA Corp", "type": "stock", "current_price": 178.9},
            ],
        )
        _put_catalog(
            s3_client,
            "etf",
            [{"ticker": "VOO", "name": "Vanguard S&P 500", "type": "etf", "current_price": 624.5}],
        )
        _put_catalog(
            s3_client,
            "fx",
            [
                {
                    "ticker": "GBPUSD",
                    "name": "British Pound to US Dollar",
                    "type": "fx",
                    "current_price": 1.27,
                }
            ],
        )

    def test_matches_ticker_substring_case_insensitively(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("voo")

        assert [r["ticker"] for r in result] == ["VOO"]

    def test_matches_name_substring(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("nvidia")

        assert [r["ticker"] for r in result] == ["NVDA"]

    def test_searches_every_asset_class_by_default(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a")

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA", "VOO", "GBPUSD"}

    def test_asset_classes_filters_the_scan(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a", asset_classes=["stock"])

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA"}

    def test_results_are_sorted_by_ticker(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a")

        assert [r["ticker"] for r in result] == sorted(r["ticker"] for r in result)

    def test_no_match_returns_empty_list(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.search("zzz") == []
