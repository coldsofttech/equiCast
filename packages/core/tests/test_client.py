import json
from datetime import UTC, datetime, timedelta
from io import BytesIO

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from equicast_core.client import PRICE_RANGES, MarketDataClient
from moto import mock_aws

BUCKET = "equicast-market-data-test"


def _parquet_bytes(rows: list[dict]) -> bytes:
    table = pa.Table.from_pylist(rows)
    buffer = BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def _price_row(
    date: str,
    *,
    close: float,
    open: float | None = None,
    high: float | None = None,
    low: float | None = None,
    currency: str = "USD",
    last_updated: str | None = None,
    source: str = "yfinance",
    ticker: str = "VOO",
) -> dict:
    """A full raw price.parquet row — every field get_prices reads
    (date/open/high/low/close for the trimmed/aggregated output;
    ticker/currency/last_updated/source for the response's top-level
    metadata), defaulting open/high/low to `close` when a test doesn't care
    about intra-day movement."""
    return {
        "ticker": ticker,
        "currency": currency,
        "date": date,
        "open": open if open is not None else close,
        "high": high if high is not None else close,
        "low": low if low is not None else close,
        "close": close,
        "average": close,
        "last_updated": last_updated or f"{date}T21:00:00+00:00",
        "source": source,
    }


def _put_year(s3_client, asset_class: str, symbol: str, year: int, rows: list[dict]) -> None:
    """Writes `rows` to whichever of `price/current.parquet` (this calendar
    year) or `price/history.parquet` (any earlier year) `year` belongs to —
    matching `equicast_stock.writer.write_price_parquet`'s split. Multiple
    calls for different past years accumulate into the same
    `history.parquet` (mirroring a `--full-load` run merging every prior
    year into one file) rather than each call overwriting the last."""
    current_year = datetime.now(UTC).year
    filename = "current.parquet" if year == current_year else "history.parquet"
    key = f"{asset_class}={symbol}/price/{filename}"
    if filename == "history.parquet":
        try:
            existing = s3_client.get_object(Bucket=BUCKET, Key=key)
        except s3_client.exceptions.NoSuchKey:
            pass
        else:
            table = pq.read_table(BytesIO(existing["Body"].read()))
            rows = table.to_pylist() + rows
    s3_client.put_object(Bucket=BUCKET, Key=key, Body=_parquet_bytes(rows))


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


class TestGetPrices:
    def test_price_ranges_are_exactly(self) -> None:
        assert PRICE_RANGES == ("1d", "5d", "1m", "6m", "ytd", "1y", "2y", "3y", "5y", "10y", "max")

    def test_returns_dict_shape_with_trimmed_price_rows(self, s3_client) -> None:
        # "ytd" (daily granularity, no aggregation) rather than the default
        # "max" — two same-month rows would otherwise collapse into one
        # monthly bar (see test_max_aggregates_same_calendar_month_rows_
        # into_one_bar), which isn't what this test is checking.
        year = datetime.now(UTC).year
        rows = [
            _price_row(f"{year}-01-02", close=624.5),
            _price_row(f"{year}-01-05", close=628.64, last_updated=f"{year}-01-05T21:05:00+00:00"),
        ]
        _put_year(s3_client, "etf", "VOO", year, rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range="ytd")

        assert result["ticker"] == "VOO"
        assert result["currency"] == "USD"
        assert result["last_updated"] == rows[-1]["last_updated"]
        assert result["source"] == "yfinance"
        assert result["prices"] == [
            {
                "date": r["date"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
            }
            for r in rows
        ]

    def test_returns_empty_shape_when_nothing_published(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_prices("etf", "MISSING") == {
            "ticker": "MISSING",
            "currency": None,
            "last_updated": None,
            "source": None,
            "prices": [],
        }

    def test_default_range_lists_and_reads_every_published_year(self, s3_client) -> None:
        year = datetime.now(UTC).year
        for y, close in ((year - 2, 500.0), (year - 1, 550.0), (year, 600.0)):
            _put_year(s3_client, "etf", "VOO", y, [_price_row(f"{y}-03-01", close=close)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo")

        assert [p["date"] for p in result["prices"]] == [
            f"{year - 2}-03-01",
            f"{year - 1}-03-01",
            f"{year}-03-01",
        ]

    def test_1d_returns_only_the_latest_row(self, s3_client) -> None:
        year = datetime.now(UTC).year
        rows = [_price_row(f"{year}-01-0{d}", close=float(d)) for d in range(1, 4)]
        _put_year(s3_client, "etf", "VOO", year, rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range="1d")

        assert [p["date"] for p in result["prices"]] == [f"{year}-01-03"]

    def test_5d_can_span_into_the_prior_year(self, s3_client) -> None:
        today = datetime.now(UTC).date()
        days = [today - timedelta(days=offset) for offset in range(4, -1, -1)]
        by_year: dict[int, list[dict]] = {}
        for d in days:
            by_year.setdefault(d.year, []).append(_price_row(d.isoformat(), close=1.0))
        for y, rows in by_year.items():
            _put_year(s3_client, "etf", "VOO", y, rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range="5d")

        assert [p["date"] for p in result["prices"]] == [d.isoformat() for d in days]

    def test_ytd_excludes_prior_year_rows(self, s3_client) -> None:
        year = datetime.now(UTC).year
        _put_year(s3_client, "etf", "VOO", year - 1, [_price_row(f"{year - 1}-12-31", close=1.0)])
        _put_year(s3_client, "etf", "VOO", year, [_price_row(f"{year}-01-02", close=2.0)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range="ytd")

        assert [p["date"] for p in result["prices"]] == [f"{year}-01-02"]

    def test_1y_excludes_rows_older_than_a_year(self, s3_client) -> None:
        today = datetime.now(UTC).date()
        old = today - timedelta(days=400)
        recent = today - timedelta(days=30)
        by_year: dict[int, list[dict]] = {}
        by_year.setdefault(old.year, []).append(_price_row(old.isoformat(), close=1.0))
        by_year.setdefault(recent.year, []).append(_price_row(recent.isoformat(), close=2.0))
        for y, rows in by_year.items():
            _put_year(s3_client, "etf", "VOO", y, rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range="1y")

        dates = [p["date"] for p in result["prices"]]
        assert recent.isoformat() in dates
        assert old.isoformat() not in dates

    @pytest.mark.parametrize("price_range", ["1y", "2y"])
    def test_1y_and_2y_aggregate_same_iso_week_rows_into_one_friday_bar(
        self, s3_client, price_range
    ) -> None:
        today = datetime.now(UTC).date()
        monday = today - timedelta(days=today.weekday())
        days = [monday, monday + timedelta(days=1), monday + timedelta(days=2)]
        rows = [
            _price_row(days[0].isoformat(), open=10, high=12, low=9, close=11),
            _price_row(days[1].isoformat(), open=11, high=15, low=10, close=14),
            _price_row(days[2].isoformat(), open=14, high=14.5, low=13, close=13.5),
        ]
        by_year: dict[int, list[dict]] = {}
        for d, row in zip(days, rows):
            by_year.setdefault(d.year, []).append(row)
        for y, year_rows in by_year.items():
            _put_year(s3_client, "etf", "VOO", y, year_rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range=price_range)

        # The bucket's date/close land on its last trading day in the
        # group (Friday for a normal Mon-Wed fixture like this one, since
        # there's no Thu/Fri row to extend the group further).
        assert result["prices"] == [
            {"date": days[2].isoformat(), "open": 10, "high": 15, "low": 9, "close": 13.5}
        ]

    @pytest.mark.parametrize("price_range", ["3y", "5y", "10y", "max"])
    def test_3y_and_up_aggregate_same_calendar_month_rows_into_one_bar(
        self, s3_client, price_range
    ) -> None:
        first_of_month = datetime.now(UTC).date().replace(day=1)
        days = [
            first_of_month,
            first_of_month + timedelta(days=10),
            first_of_month + timedelta(days=20),
        ]
        rows = [
            _price_row(days[0].isoformat(), open=100, high=105, low=98, close=102),
            _price_row(days[1].isoformat(), open=102, high=110, low=101, close=108),
            _price_row(days[2].isoformat(), open=108, high=109, low=95, close=99),
        ]
        _put_year(s3_client, "etf", "VOO", first_of_month.year, rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("etf", "voo", price_range=price_range)

        # The bucket's date/close land on its last trading day in the
        # month, i.e. end-of-month.
        assert result["prices"] == [
            {"date": days[2].isoformat(), "open": 100, "high": 110, "low": 95, "close": 99}
        ]

    def test_unknown_range_raises_value_error(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        with pytest.raises(ValueError):
            client.get_prices("etf", "voo", price_range="3d")


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
