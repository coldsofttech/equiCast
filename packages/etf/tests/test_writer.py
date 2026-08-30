from pathlib import Path

import pandas as pd
from equicast_etf.writer import write_price_parquet, write_profile_parquet


def test_write_profile_parquet_partitions_by_ticker(tmp_path: Path) -> None:
    profile = {
        "ticker": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "quote_type": "ETF",
        "exchange": "PCX",
        "currency": "USD",
        "description": "Tracks the S&P 500 Index.",
        "category": "Large Blend",
        "fund_family": "Vanguard",
        "website": "https://www.vanguard.com",
        "beta": 1.0,
        "expense_ratio": 0.03,
        "dividend_rate": None,
        "dividend_yield": 0.0107,
        "total_assets": 1686884319232,
        "nav_price": 708.98,
        "volume": 8067208,
        "day_open": 709.39,
        "day_high": 712.6692,
        "day_low": 706.26,
        "day_close": 707.24,
        "day_average": 709.4646,
        "year_open": 588.29198719,
        "year_high": 716.39,
        "year_low": 578.46,
        "year_close": 707.24,
        "year_average": 647.425,
        "moving_average_50_days": 693.1996,
        "moving_average_200_days": 652.7322,
        "ytd_return": 10.11602,
        "three_year_average_return": 0.2217858,
        "five_year_average_return": 0.1294499,
        "inception_date": "2010-09-07T00:00:00+00:00",
        "last_updated": "2026-08-28T20:00:00+00:00",
        "source": "yfinance",
    }

    path = write_profile_parquet(profile, tmp_path)

    assert path == tmp_path / "etf=VOO" / "profile.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [profile]


def _price_record(date: str, **overrides) -> dict:
    record = {
        "ticker": "VOO",
        "currency": "USD",
        "date": date,
        "open": 700.10,
        "high": 702.50,
        "low": 698.00,
        "close": 701.30,
        "average": 700.25,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def test_write_price_parquet_partitions_by_ticker_and_year(tmp_path: Path) -> None:
    records = [
        _price_record("2025-12-30"),
        _price_record("2025-12-31"),
        _price_record("2026-01-02"),
    ]

    paths = write_price_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "etf=VOO" / "year=2025" / "price.parquet",
        tmp_path / "etf=VOO" / "year=2026" / "price.parquet",
    }

    year_2025 = pd.read_parquet(tmp_path / "etf=VOO" / "year=2025" / "price.parquet")
    assert sorted(year_2025["date"]) == ["2025-12-30", "2025-12-31"]

    year_2026 = pd.read_parquet(tmp_path / "etf=VOO" / "year=2026" / "price.parquet")
    assert year_2026.to_dict(orient="records") == [records[2]]


def test_write_price_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_price_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []
