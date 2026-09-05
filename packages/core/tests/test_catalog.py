import json
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from equicast_core.catalog import build_catalog_rows, catalog_key, main, upload_catalog
from moto import mock_aws

BUCKET = "equicast-market-data-test"


def _write_profile(output_dir: Path, asset_class: str, ticker: str, profile: dict) -> None:
    directory = output_dir / f"{asset_class}={ticker}"
    directory.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([profile])
    pq.write_table(table, directory / "profile.parquet")


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_catalog_key_is_lowercased_and_namespaced() -> None:
    assert catalog_key("STOCK") == "catalog/stock.json"


class TestBuildCatalogRows:
    def test_builds_one_row_per_ticker_stock_shape(self, tmp_path: Path) -> None:
        _write_profile(
            tmp_path,
            "stock",
            "AAPL",
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "day_close": 227.5,
                "website": "https://www.apple.com",
            },
        )
        _write_profile(
            tmp_path,
            "stock",
            "MSFT",
            {
                "ticker": "MSFT",
                "name": "Microsoft Corp",
                "day_close": 410.1,
                "website": "https://www.microsoft.com",
            },
        )

        rows = build_catalog_rows(tmp_path, "stock")

        assert rows == [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "type": "stock",
                "current_price": 227.5,
                "website": "https://www.apple.com",
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft Corp",
                "type": "stock",
                "current_price": 410.1,
                "website": "https://www.microsoft.com",
            },
        ]

    def test_derives_ticker_from_directory_name_for_fx_shape(self, tmp_path: Path) -> None:
        _write_profile(
            tmp_path,
            "fx",
            "GBPUSD",
            {
                "from_currency": "GBP",
                "to_currency": "USD",
                "description": "British Pound to US Dollar",
                "day_close": 1.27,
            },
        )

        rows = build_catalog_rows(tmp_path, "fx")

        assert rows == [
            {
                "ticker": "GBPUSD",
                "name": "British Pound to US Dollar",
                "type": "fx",
                "current_price": 1.27,
                "website": None,
            }
        ]

    def test_only_matches_the_given_asset_class(self, tmp_path: Path) -> None:
        _write_profile(tmp_path, "stock", "AAPL", {"ticker": "AAPL", "name": "Apple Inc."})
        _write_profile(tmp_path, "etf", "VOO", {"ticker": "VOO", "name": "Vanguard S&P 500"})

        assert [r["ticker"] for r in build_catalog_rows(tmp_path, "stock")] == ["AAPL"]
        assert [r["ticker"] for r in build_catalog_rows(tmp_path, "etf")] == ["VOO"]

    def test_returns_empty_list_when_nothing_matches(self, tmp_path: Path) -> None:
        assert build_catalog_rows(tmp_path, "stock") == []

    def test_sorted_by_ticker(self, tmp_path: Path) -> None:
        _write_profile(tmp_path, "stock", "TSLA", {"ticker": "TSLA", "name": "Tesla"})
        _write_profile(tmp_path, "stock", "AAPL", {"ticker": "AAPL", "name": "Apple Inc."})

        rows = build_catalog_rows(tmp_path, "stock")

        assert [r["ticker"] for r in rows] == ["AAPL", "TSLA"]


class TestUploadCatalog:
    def test_uploads_the_rows_as_json(self, s3_client) -> None:
        rows = [{"ticker": "AAPL", "name": "Apple Inc.", "type": "stock", "current_price": 227.5}]

        upload_catalog(BUCKET, "stock", rows, s3_client=s3_client)

        response = s3_client.get_object(Bucket=BUCKET, Key="catalog/stock.json")
        assert json.loads(response["Body"].read()) == {"tickers": rows}

    def test_replaces_a_previous_catalog_outright(self, s3_client) -> None:
        upload_catalog(BUCKET, "stock", [{"ticker": "OLD"}], s3_client=s3_client)

        upload_catalog(BUCKET, "stock", [{"ticker": "NEW"}], s3_client=s3_client)

        response = s3_client.get_object(Bucket=BUCKET, Key="catalog/stock.json")
        assert json.loads(response["Body"].read()) == {"tickers": [{"ticker": "NEW"}]}


def test_main_builds_and_uploads_end_to_end(tmp_path: Path, s3_client, monkeypatch) -> None:
    _write_profile(
        tmp_path, "etf", "VOO", {"ticker": "VOO", "name": "Vanguard S&P 500", "day_close": 624.5}
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "equicast-core-build-catalog",
            "--asset-class",
            "etf",
            "--output-dir",
            str(tmp_path),
            "--bucket",
            BUCKET,
        ],
    )
    monkeypatch.setattr("equicast_core.catalog.boto3.client", lambda *a, **kw: s3_client)

    main()

    response = s3_client.get_object(Bucket=BUCKET, Key="catalog/etf.json")
    assert json.loads(response["Body"].read()) == {
        "tickers": [
            {
                "ticker": "VOO",
                "name": "Vanguard S&P 500",
                "type": "etf",
                "current_price": 624.5,
                "website": None,
            }
        ]
    }
