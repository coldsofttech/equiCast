import json
from datetime import UTC, datetime, timedelta
from io import BytesIO

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from equicast_core.catalog import CATALOG_SCHEMA, upload_catalog
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


def _fx_row(date: str, *, close: float, last_updated: str | None = None) -> dict:
    """A raw fx price.parquet row — no `currency` field at all (a pair
    converts *between* two currencies rather than being priced *in* one,
    see equicast_fx.writer); get_price_on_date/get_fx_rate_on_date only
    ever read `date`/`close` off this shape, nothing pair-identifying."""
    return {
        "date": date,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "last_updated": last_updated or f"{date}T21:00:00+00:00",
        "source": "yfinance",
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


def test_get_metrics_returns_the_single_row(s3_client) -> None:
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/metrics.parquet",
        Body=_parquet_bytes([{"volatility": 0.23, "trailing_pe": 28.5}]),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_metrics("stock", "aapl") == {"volatility": 0.23, "trailing_pe": 28.5}


def test_get_metrics_returns_none_when_key_missing(s3_client) -> None:
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    assert client.get_metrics("stock", "MISSING") is None


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


def _dividend_row(
    ex_dividend_date: str,
    *,
    price: float = 0.26,
    currency: str = "USD",
    last_updated: str | None = None,
    source: str = "yfinance",
    ticker: str = "AAPL",
    payment_date: str | None = None,
) -> dict:
    row = {
        "ticker": ticker,
        "currency": currency,
        "ex_dividend_date": ex_dividend_date,
        "price": price,
        "last_updated": last_updated or f"{ex_dividend_date}T21:00:00+00:00",
        "source": source,
    }
    if payment_date is not None:
        row["payment_date"] = payment_date
    return row


def test_get_dividends_returns_none_when_nothing_published(s3_client) -> None:
    client = MarketDataClient(BUCKET, s3_client=s3_client)
    assert client.get_dividends("stock", "AAPL") is None


def test_get_dividends_combines_paid_declared_and_estimated_rows(s3_client) -> None:
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/dividend/history.parquet",
        Body=_parquet_bytes(
            [_dividend_row("2025-02-10", last_updated="2026-08-30T09:00:00+00:00")]
        ),
    )
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/dividend/current.parquet",
        Body=_parquet_bytes(
            [_dividend_row("2026-02-10", last_updated="2026-08-30T09:00:01+00:00")]
        ),
    )
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/dividend/future.parquet",
        Body=_parquet_bytes(
            [
                _dividend_row(
                    "2026-09-10",
                    payment_date="2026-09-20",
                    last_updated="2026-08-30T09:00:02+00:00",
                )
            ]
        ),
    )
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/forecasting/dividends.parquet",
        Body=_parquet_bytes(
            [
                _dividend_row(
                    "2026-12-10", source="equicast", last_updated="2026-08-30T09:00:03+00:00"
                )
            ]
        ),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    result = client.get_dividends("stock", "aapl")

    assert result == {
        "ticker": "AAPL",
        "currency": "USD",
        "last_updated": "2026-08-30T09:00:03+00:00",
        "dividends": [
            {
                "ticker": "AAPL",
                "currency": "USD",
                "ex_dividend_date": "2025-02-10",
                "payment_date": None,
                "price": 0.26,
                "status": "paid",
                "last_updated": "2026-08-30T09:00:00+00:00",
                "source": "yfinance",
            },
            {
                "ticker": "AAPL",
                "currency": "USD",
                "ex_dividend_date": "2026-02-10",
                "payment_date": None,
                "price": 0.26,
                "status": "paid",
                "last_updated": "2026-08-30T09:00:01+00:00",
                "source": "yfinance",
            },
            {
                "ticker": "AAPL",
                "currency": "USD",
                "ex_dividend_date": "2026-09-10",
                "payment_date": "2026-09-20",
                "price": 0.26,
                "status": "declared",
                "last_updated": "2026-08-30T09:00:02+00:00",
                "source": "yfinance",
            },
            {
                "ticker": "AAPL",
                "currency": "USD",
                "ex_dividend_date": "2026-12-10",
                "payment_date": None,
                "price": 0.26,
                "status": "estimated",
                "last_updated": "2026-08-30T09:00:03+00:00",
                "source": "equicast",
            },
        ],
    }


def test_get_dividends_declared_row_with_no_payment_date_yet(s3_client) -> None:
    s3_client.put_object(
        Bucket=BUCKET,
        Key="stock=AAPL/dividend/future.parquet",
        Body=_parquet_bytes([_dividend_row("2026-09-10", payment_date=None)]),
    )
    client = MarketDataClient(BUCKET, s3_client=s3_client)

    result = client.get_dividends("stock", "AAPL")

    assert result["dividends"][0]["payment_date"] is None


class TestGetPrices:
    def test_price_ranges_are_exactly(self) -> None:
        assert PRICE_RANGES == ("1d", "5d", "1m", "6m", "ytd", "1y", "2y", "3y", "5y", "10y", "max")

    def test_currency_is_none_when_price_rows_carry_no_currency_field(self, s3_client) -> None:
        # fx's price rows carry from_currency/to_currency instead of a
        # single `currency` (see equicast_fx.writer) — get_prices must
        # degrade to `None` here rather than KeyError.
        year = datetime.now(UTC).year
        row = {
            "from_currency": "GBP",
            "to_currency": "USD",
            "date": f"{year}-01-02",
            "open": 1.3,
            "high": 1.31,
            "low": 1.29,
            "close": 1.305,
            "last_updated": "2026-01-02T21:00:00+00:00",
            "source": "yfinance",
        }
        _put_year(s3_client, "fx", "GBPUSD", year, [row])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_prices("fx", "GBPUSD", price_range="ytd")

        assert result["currency"] is None
        assert result["prices"] == [
            {
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
            }
        ]

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


class TestGetPriceOnDate:
    def test_exact_date_match(self, s3_client) -> None:
        year = datetime.now(UTC).year
        _put_year(
            s3_client,
            "etf",
            "VOO",
            year,
            [_price_row(f"{year}-01-02", close=100.0), _price_row(f"{year}-01-03", close=101.0)],
        )
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_price_on_date("etf", "voo", f"{year}-01-03")

        assert result == {"date": f"{year}-01-03", "close": 101.0, "currency": "USD"}

    def test_falls_back_to_nearest_prior_trading_day_when_on_date_has_no_row(
        self, s3_client
    ) -> None:
        year = datetime.now(UTC).year
        _put_year(s3_client, "etf", "VOO", year, [_price_row(f"{year}-01-03", close=101.0)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        # "-05" has no row of its own (e.g. a weekend/holiday) — resolves to
        # the nearest earlier published trading day instead.
        result = client.get_price_on_date("etf", "voo", f"{year}-01-05")

        assert result == {"date": f"{year}-01-03", "close": 101.0, "currency": "USD"}

    def test_reads_history_parquet_when_on_date_is_in_a_prior_year(self, s3_client) -> None:
        year = datetime.now(UTC).year
        _put_year(s3_client, "etf", "VOO", year - 1, [_price_row(f"{year - 1}-06-15", close=90.0)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_price_on_date("etf", "voo", f"{year - 1}-06-20")

        assert result == {"date": f"{year - 1}-06-15", "close": 90.0, "currency": "USD"}

    def test_returns_none_when_nothing_published_on_or_before_on_date(self, s3_client) -> None:
        year = datetime.now(UTC).year
        _put_year(s3_client, "etf", "VOO", year, [_price_row(f"{year}-06-15", close=90.0)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_price_on_date("etf", "voo", f"{year}-01-01") is None

    def test_returns_none_when_no_data_published_at_all(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_price_on_date("etf", "MISSING", "2026-01-01") is None

    def test_currency_is_none_for_fx_rows(self, s3_client) -> None:
        year = datetime.now(UTC).year
        _put_year(s3_client, "fx", "GBPUSD", year, [_fx_row(f"{year}-01-02", close=1.305)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_price_on_date("fx", "GBPUSD", f"{year}-01-02")

        assert result == {"date": f"{year}-01-02", "close": 1.305, "currency": None}


class TestGetFxRateOnDate:
    def test_same_currency_returns_one_with_no_lookup(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        # No fx data seeded at all — proves this never even attempts a
        # lookup when the two currencies are identical.
        assert client.get_fx_rate_on_date("GBP", "GBP", "2026-01-01") == 1.0

    def test_uses_the_direct_pair_when_published(self, s3_client) -> None:
        year = datetime.now(UTC).year
        _put_year(s3_client, "fx", "USDGBP", year, [_fx_row(f"{year}-01-02", close=0.8)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_fx_rate_on_date("USD", "GBP", f"{year}-01-02") == 0.8

    def test_falls_back_to_the_inverted_pair_when_direct_is_missing(self, s3_client) -> None:
        year = datetime.now(UTC).year
        # Only GBPUSD is published (1 GBP = 1.25 USD) — converting USD->GBP
        # needs the reciprocal.
        _put_year(s3_client, "fx", "GBPUSD", year, [_fx_row(f"{year}-01-02", close=1.25)])
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.get_fx_rate_on_date("USD", "GBP", f"{year}-01-02")

        assert result == pytest.approx(1 / 1.25)

    def test_returns_none_when_neither_pair_is_published(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_fx_rate_on_date("USD", "GBP", "2026-01-01") is None


def _put_catalog(s3_client, asset_class: str, rows: list[dict]) -> None:
    upload_catalog(BUCKET, asset_class, rows, s3_client=s3_client)


class TestGetCatalog:
    def test_returns_the_published_rows(self, s3_client) -> None:
        rows = [{"ticker": "AAPL", "name": "Apple Inc.", "type": "stock", "current_price": 227.5}]
        _put_catalog(s3_client, "stock", rows)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        expected = {field.name: None for field in CATALOG_SCHEMA}
        expected.update(rows[0])
        assert client.get_catalog("stock") == [expected]

    def test_returns_empty_list_when_no_catalog_published_yet(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.get_catalog("stock") == []


class TestEnrichHoldings:
    def test_returns_empty_list_unchanged(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.enrich_holdings([], "USD") == []

    def test_merges_catalog_fields_and_skips_conversion_when_same_currency(self, s3_client) -> None:
        _put_catalog(
            s3_client,
            "etf",
            [
                {
                    "ticker": "VOO",
                    "name": "Vanguard S&P 500 ETF",
                    "current_price": 450.0,
                    "currency": "USD",
                    "website": "https://investor.vanguard.com",
                    "sector": None,
                    "industry": None,
                    "last_updated": "2026-08-30T09:00:00+00:00",
                }
            ],
        )
        client = MarketDataClient(BUCKET, s3_client=s3_client)
        holding = {"id": "h-1", "ticker": "VOO", "asset_class": "etf"}

        [enriched] = client.enrich_holdings([holding], "USD")

        assert enriched == {
            **holding,
            "name": "Vanguard S&P 500 ETF",
            "sector": None,
            "industry": None,
            "website": "https://investor.vanguard.com",
            "current_price_native": 450.0,
            "current_price": 450.0,
            "last_updated": "2026-08-30T09:00:00+00:00",
        }

    def test_converts_current_price_using_the_direct_fx_pair(self, s3_client) -> None:
        _put_catalog(
            s3_client, "stock", [{"ticker": "AAPL", "current_price": 190.0, "currency": "USD"}]
        )
        _put_catalog(s3_client, "fx", [{"ticker": "USDGBP", "current_price": 0.8}])
        client = MarketDataClient(BUCKET, s3_client=s3_client)
        holding = {"id": "h-1", "ticker": "AAPL", "asset_class": "stock"}

        [enriched] = client.enrich_holdings([holding], "GBP")

        assert enriched["current_price_native"] == 190.0
        assert enriched["current_price"] == pytest.approx(190.0 * 0.8)

    def test_converts_current_price_using_the_inverted_fx_pair_when_direct_is_missing(
        self, s3_client
    ) -> None:
        _put_catalog(
            s3_client, "stock", [{"ticker": "AAPL", "current_price": 190.0, "currency": "USD"}]
        )
        # Only GBPUSD is published (1 GBP = 1.25 USD) — converting USD->GBP
        # needs the reciprocal.
        _put_catalog(s3_client, "fx", [{"ticker": "GBPUSD", "current_price": 1.25}])
        client = MarketDataClient(BUCKET, s3_client=s3_client)
        holding = {"id": "h-1", "ticker": "AAPL", "asset_class": "stock"}

        [enriched] = client.enrich_holdings([holding], "GBP")

        assert enriched["current_price"] == pytest.approx(190.0 / 1.25)

    def test_returns_none_fields_when_ticker_has_no_catalog_row(self, s3_client) -> None:
        client = MarketDataClient(BUCKET, s3_client=s3_client)
        holding = {"id": "h-1", "ticker": "UNKNOWN", "asset_class": "stock"}

        [enriched] = client.enrich_holdings([holding], "USD")

        assert enriched["name"] is None
        assert enriched["current_price_native"] is None
        assert enriched["current_price"] is None
        assert enriched["last_updated"] is None

    def test_returns_none_current_price_when_no_fx_rate_is_published(self, s3_client) -> None:
        _put_catalog(
            s3_client, "stock", [{"ticker": "AAPL", "current_price": 190.0, "currency": "USD"}]
        )
        client = MarketDataClient(BUCKET, s3_client=s3_client)
        holding = {"id": "h-1", "ticker": "AAPL", "asset_class": "stock"}

        [enriched] = client.enrich_holdings([holding], "GBP")

        assert enriched["current_price_native"] == 190.0
        assert enriched["current_price"] is None

    def test_reads_each_distinct_asset_class_catalog_once(self, s3_client, monkeypatch) -> None:
        _put_catalog(
            s3_client, "stock", [{"ticker": "AAPL", "current_price": 190.0, "currency": "USD"}]
        )
        _put_catalog(
            s3_client, "etf", [{"ticker": "VOO", "current_price": 450.0, "currency": "USD"}]
        )
        client = MarketDataClient(BUCKET, s3_client=s3_client)
        calls = []
        original = client.get_catalog

        def counting_get_catalog(asset_class):
            calls.append(asset_class)
            return original(asset_class)

        monkeypatch.setattr(client, "get_catalog", counting_get_catalog)
        holdings = [
            {"id": "h-1", "ticker": "AAPL", "asset_class": "stock"},
            {"id": "h-2", "ticker": "AAPL", "asset_class": "stock"},
            {"id": "h-3", "ticker": "VOO", "asset_class": "etf"},
        ]

        client.enrich_holdings(holdings, "USD")

        assert sorted(calls) == ["etf", "fx", "stock"]


class TestSearch:
    def _seed(self, s3_client) -> None:
        _put_catalog(
            s3_client,
            "stock",
            [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "type": "stock",
                    "current_price": 227.5,
                    "market_cap": 3_400_000_000_000,
                    "exchange": "NMS",
                    "region": "us",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                },
                {
                    "ticker": "NVDA",
                    "name": "NVIDIA Corp",
                    "type": "stock",
                    "current_price": 178.9,
                    "market_cap": 4_300_000_000_000,
                    "exchange": "NMS",
                    "region": "us",
                    "sector": "Technology",
                    "industry": "Semiconductors",
                },
                {
                    "ticker": "HSBA",
                    "name": "HSBC Holdings",
                    "type": "stock",
                    "current_price": 8.9,
                    "market_cap": 150_000_000_000,
                    "exchange": "LSE",
                    "region": "gb",
                    "sector": "Financial Services",
                    "industry": "Banks—Diversified",
                },
            ],
        )
        _put_catalog(
            s3_client,
            "etf",
            [
                {
                    "ticker": "VOO",
                    "name": "Vanguard S&P 500",
                    "type": "etf",
                    "current_price": 624.5,
                    "market_cap": 500_000_000_000,
                    "exchange": "PCX",
                    "region": "us",
                    "sector": None,
                    "industry": None,
                }
            ],
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
                    "market_cap": None,
                    "exchange": None,
                    "region": None,
                    "sector": None,
                    "industry": None,
                }
            ],
        )
        _put_catalog(
            s3_client,
            "benchmark",
            [
                {
                    "ticker": "NASDAQ100",
                    "name": "Nasdaq 100",
                    "type": "benchmark",
                    "current_price": 22400.5,
                    "market_cap": None,
                    "exchange": "NGM",
                    "region": "us",
                    "sector": None,
                    "industry": None,
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

        # "NASDAQ100" (the seeded benchmark row) matches "a" too, but the
        # default scan deliberately excludes benchmark — see
        # DEFAULT_SEARCH_ASSET_CLASSES's docstring.
        assert {r["ticker"] for r in result} == {"AAPL", "NVDA", "HSBA", "VOO", "GBPUSD"}

    def test_asset_classes_filters_the_scan(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a", asset_classes=["stock"])

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA", "HSBA"}

    def test_benchmark_is_excluded_from_the_default_scan(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("nasdaq")

        assert result == []

    def test_asset_classes_can_explicitly_include_benchmark(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("nasdaq", asset_classes=["benchmark"])

        assert {r["ticker"] for r in result} == {"NASDAQ100"}

    def test_results_are_sorted_by_ticker(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a")

        assert [r["ticker"] for r in result] == sorted(r["ticker"] for r in result)

    def test_no_match_returns_empty_list(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.search("zzz") == []

    def test_market_cap_range_filters_stock_and_etf(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        # "a" also matches GBPUSD's name ("... to US Dollar"), but fx has no
        # market_cap concept (always None) — excluded whenever a bound is
        # given, same as a stock/etf row with no market_cap resolved (see
        # test_market_cap_filter_excludes_fx below for a targeted check).
        result = client.search("a", min_market_cap=1_000_000_000_000)

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA"}

    def test_market_cap_range_is_inclusive_on_both_ends(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search(
            "a", min_market_cap=3_400_000_000_000, max_market_cap=3_400_000_000_000
        )

        assert {r["ticker"] for r in result} == {"AAPL"}

    def test_market_cap_filter_excludes_fx(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("gbp", min_market_cap=1_000_000_000_000)

        assert result == []

    def test_market_cap_filter_excludes_a_stock_with_no_market_cap_resolved(
        self, s3_client
    ) -> None:
        _put_catalog(
            s3_client,
            "stock",
            [{"ticker": "NEWCO", "name": "New Co", "type": "stock", "market_cap": None}],
        )
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        assert client.search("newco", min_market_cap=1) == []

    def test_market_cap_filter_excludes_a_benchmark_with_no_market_cap_concept(
        self, s3_client
    ) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("nasdaq", asset_classes=["benchmark"], min_market_cap=1)

        assert result == []

    def test_no_market_cap_bounds_leaves_every_asset_class_unfiltered(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a")

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA", "HSBA", "VOO", "GBPUSD"}

    def test_exchange_filters_stock_and_etf_case_insensitively(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        # "a" also matches GBPUSD's name ("... US Dollar"), but fx has no
        # exchange concept (always None) — excluded whenever an exchange is
        # given (see test_exchange_filter_excludes_fx for a targeted check).
        result = client.search("a", exchange="nms")

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA"}

    def test_exchange_filter_excludes_fx(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("gbp", exchange="LSE")

        assert result == []

    def test_exchange_filter_excludes_a_row_on_a_different_exchange(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("hsba", exchange="NMS")

        assert result == []

    def test_region_filters_stock_and_etf_case_insensitively(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        # "a" also matches GBPUSD's name, but fx has no region concept
        # (always None) — excluded whenever a region is given (see
        # test_region_filter_excludes_fx for a targeted check).
        result = client.search("a", region="GB")

        assert {r["ticker"] for r in result} == {"HSBA"}

    def test_region_filter_excludes_fx(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("gbp", region="gb")

        assert result == []

    def test_exchange_and_region_filters_combine(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a", exchange="NMS", region="us")

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA"}

    def test_sector_filters_stock_case_insensitively(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        # "a" also matches GBPUSD's name ("... US Dollar"), but fx has no
        # sector concept (always None) — excluded whenever a sector is
        # given (see test_sector_filter_excludes_fx for a targeted check).
        result = client.search("a", sector="technology")

        assert {r["ticker"] for r in result} == {"AAPL", "NVDA"}

    def test_sector_filter_excludes_fx(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("gbp", sector="Technology")

        assert result == []

    def test_sector_filter_excludes_a_row_in_a_different_sector(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("hsba", sector="Technology")

        assert result == []

    def test_sector_filter_excludes_an_etf_row_with_no_sector(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("voo", sector="Technology")

        assert result == []

    def test_industry_filters_stock_case_insensitively(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("nvda", industry="semiconductors")

        assert {r["ticker"] for r in result} == {"NVDA"}

    def test_industry_filter_excludes_fx(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("gbp", industry="Semiconductors")

        assert result == []

    def test_sector_and_industry_filters_combine(self, s3_client) -> None:
        self._seed(s3_client)
        client = MarketDataClient(BUCKET, s3_client=s3_client)

        result = client.search("a", sector="Technology", industry="Semiconductors")

        assert {r["ticker"] for r in result} == {"NVDA"}
