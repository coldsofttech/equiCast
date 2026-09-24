from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from botocore.exceptions import ClientError
from equicast_core.catalog import (
    build_catalog_rows,
    catalog_key,
    download_catalog_rows,
    main,
    merge_catalog_rows,
    upload_catalog,
)
from moto import mock_aws

BUCKET = "equicast-market-data-test"


def _write_profile(output_dir: Path, asset_class: str, ticker: str, profile: dict) -> None:
    directory = output_dir / f"{asset_class}={ticker}"
    directory.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([profile])
    pq.write_table(table, directory / "profile.parquet")


def _read_catalog(s3_client, key: str) -> list[dict]:
    response = s3_client.get_object(Bucket=BUCKET, Key=key)
    return pq.read_table(pa.BufferReader(response["Body"].read())).to_pylist()


#: Every CATALOG_SCHEMA column, `None`-defaulted — a row written through
#: upload_catalog() always round-trips with every column present, even one
#: built from a partial test dict, so expected rows in these tests spell
#: out the full shape rather than just the fields the test cares about.
_EMPTY_ROW = {
    "ticker": None,
    "name": None,
    "type": None,
    "current_price": None,
    "currency": None,
    "website": None,
    "market_cap": None,
    "exchange": None,
    "region": None,
    "sector": None,
    "industry": None,
    "isin": None,
    "tax_domicile": None,
    "last_updated": None,
}


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
    assert catalog_key("STOCK") == "catalog/stock.parquet"


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
                "currency": "USD",
                "website": "https://www.apple.com",
                "market_cap": 3_400_000_000_000,
                "exchange": "NMS",
                "region": "us",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "last_updated": "2026-08-30T09:00:00+00:00",
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
                "currency": "USD",
                "website": "https://www.microsoft.com",
                "market_cap": 3_050_000_000_000,
                "exchange": "NMS",
                "region": "us",
                "sector": "Technology",
                "industry": "Software—Infrastructure",
                "last_updated": "2026-08-29T09:00:00+00:00",
            },
        )

        rows = build_catalog_rows(tmp_path, "stock")

        assert rows == [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "type": "stock",
                "current_price": 227.5,
                "currency": "USD",
                "website": "https://www.apple.com",
                "market_cap": 3_400_000_000_000,
                "exchange": "NMS",
                "region": "us",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "isin": None,
                "tax_domicile": None,
                "last_updated": "2026-08-30T09:00:00+00:00",
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft Corp",
                "type": "stock",
                "current_price": 410.1,
                "currency": "USD",
                "website": "https://www.microsoft.com",
                "market_cap": 3_050_000_000_000,
                "exchange": "NMS",
                "region": "us",
                "sector": "Technology",
                "industry": "Software—Infrastructure",
                "isin": None,
                "tax_domicile": None,
                "last_updated": "2026-08-29T09:00:00+00:00",
            },
        ]

    def test_uses_total_assets_as_market_cap_for_etf_shape(self, tmp_path: Path) -> None:
        _write_profile(
            tmp_path,
            "etf",
            "VOO",
            {
                "ticker": "VOO",
                "name": "Vanguard S&P 500",
                "day_close": 624.5,
                "currency": "USD",
                "total_assets": 500_000_000_000,
                "exchange": "PCX",
                "region": "us",
            },
        )

        rows = build_catalog_rows(tmp_path, "etf")

        assert rows[0]["market_cap"] == 500_000_000_000
        assert rows[0]["exchange"] == "PCX"
        assert rows[0]["region"] == "us"

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
                "currency": "USD",
                "website": None,
                "market_cap": None,
                "exchange": None,
                "region": None,
                "sector": None,
                "industry": None,
                "isin": None,
                "tax_domicile": None,
                "last_updated": None,
            }
        ]

    def test_carries_the_tax_domicile_field_through(self, tmp_path: Path) -> None:
        _write_profile(
            tmp_path,
            "stock",
            "AAPL",
            {"ticker": "AAPL", "name": "Apple Inc.", "isin": "US0378331005", "tax_domicile": "US"},
        )

        rows = build_catalog_rows(tmp_path, "stock")

        assert rows[0]["isin"] == "US0378331005"
        assert rows[0]["tax_domicile"] == "US"

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
    def test_uploads_the_rows_as_parquet(self, s3_client) -> None:
        rows = [{"ticker": "AAPL", "name": "Apple Inc.", "type": "stock", "current_price": 227.5}]

        upload_catalog(BUCKET, "stock", rows, s3_client=s3_client)

        result = _read_catalog(s3_client, "catalog/stock.parquet")
        assert result == [
            {
                **_EMPTY_ROW,
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "type": "stock",
                "current_price": 227.5,
            }
        ]

    def test_replaces_a_previous_catalog_outright(self, s3_client) -> None:
        upload_catalog(BUCKET, "stock", [{"ticker": "OLD"}], s3_client=s3_client)

        upload_catalog(BUCKET, "stock", [{"ticker": "NEW"}], s3_client=s3_client)

        result = _read_catalog(s3_client, "catalog/stock.parquet")
        assert result == [{**_EMPTY_ROW, "ticker": "NEW"}]

    def test_uploads_a_valid_file_for_an_empty_ticker_list(self, s3_client) -> None:
        upload_catalog(BUCKET, "stock", [], s3_client=s3_client)

        assert _read_catalog(s3_client, "catalog/stock.parquet") == []


class TestDownloadCatalogRows:
    def test_returns_empty_list_when_catalog_does_not_exist_yet(self, s3_client) -> None:
        assert download_catalog_rows(BUCKET, "stock", s3_client=s3_client) == []

    def test_returns_the_published_rows(self, s3_client) -> None:
        upload_catalog(BUCKET, "stock", [{"ticker": "AAPL"}], s3_client=s3_client)

        assert download_catalog_rows(BUCKET, "stock", s3_client=s3_client) == [
            {**_EMPTY_ROW, "ticker": "AAPL"}
        ]


class TestMergeCatalogRows:
    def test_adds_new_tickers_to_an_empty_catalog(self) -> None:
        new_rows = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]

        assert merge_catalog_rows([], new_rows) == new_rows

    def test_replaces_only_the_matching_tickers(self) -> None:
        existing_rows = [
            {"ticker": "AAPL", "current_price": 1.0},
            {"ticker": "MSFT", "current_price": 2.0},
        ]
        new_rows = [{"ticker": "MSFT", "current_price": 3.0}]

        assert merge_catalog_rows(existing_rows, new_rows) == [
            {"ticker": "AAPL", "current_price": 1.0},
            {"ticker": "MSFT", "current_price": 3.0},
        ]

    def test_keeps_untouched_existing_tickers_and_adds_brand_new_ones(self) -> None:
        existing_rows = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
        new_rows = [{"ticker": "NWG.L"}]

        assert [r["ticker"] for r in merge_catalog_rows(existing_rows, new_rows)] == [
            "AAPL",
            "MSFT",
            "NWG.L",
        ]


def test_main_merges_into_the_existing_catalog_when_targeted(
    tmp_path: Path, s3_client, monkeypatch
) -> None:
    upload_catalog(
        BUCKET,
        "stock",
        [{"ticker": "AAPL", "name": "Apple Inc."}, {"ticker": "MSFT", "name": "Microsoft Corp"}],
        s3_client=s3_client,
    )
    _write_profile(tmp_path, "stock", "NWG.L", {"ticker": "NWG.L", "name": "NatWest Group"})
    monkeypatch.setattr(
        "sys.argv",
        [
            "equicast-core-build-catalog",
            "--asset-class",
            "stock",
            "--output-dir",
            str(tmp_path),
            "--bucket",
            BUCKET,
            "--merge",
        ],
    )
    monkeypatch.setattr("equicast_core.catalog.boto3.client", lambda *a, **kw: s3_client)

    main()

    result = _read_catalog(s3_client, "catalog/stock.parquet")
    assert sorted(r["ticker"] for r in result) == ["AAPL", "MSFT", "NWG.L"]


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

    result = _read_catalog(s3_client, "catalog/etf.parquet")
    assert result == [
        {
            **_EMPTY_ROW,
            "ticker": "VOO",
            "name": "Vanguard S&P 500",
            "type": "etf",
            "current_price": 624.5,
        }
    ]


def test_main_refuses_to_publish_an_empty_catalog(tmp_path: Path, s3_client, monkeypatch) -> None:
    """No profile.parquet found under --output-dir (e.g. a CI artifact path
    mismatch leaving it a directory too shallow) must fail the run loudly
    rather than publish an empty catalog/<asset_class>.parquet that makes
    search return nothing for every query with no error anywhere."""
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

    with pytest.raises(SystemExit):
        main()

    with pytest.raises(ClientError):
        _read_catalog(s3_client, "catalog/etf.parquet")
