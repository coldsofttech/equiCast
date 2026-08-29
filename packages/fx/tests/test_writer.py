from pathlib import Path

import pandas as pd
from equicast_fx.writer import write_price_parquet, write_profile_parquet


def test_write_profile_parquet_partitions_by_pair(tmp_path: Path) -> None:
    profile = {
        "from_currency": "GBP",
        "to_currency": "USD",
        "exchange": "CCY",
        "region": "US",
        "description": "GBP/USD",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }

    path = write_profile_parquet(profile, tmp_path)

    assert path == tmp_path / "fx=GBPUSD" / "profile.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [profile]


def _price_record(date: str, **overrides) -> dict:
    record = {
        "from_currency": "GBP",
        "to_currency": "USD",
        "date": date,
        "open": 1.30,
        "high": 1.31,
        "low": 1.29,
        "close": 1.305,
        "average": 1.30,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def test_write_price_parquet_partitions_by_pair_and_year(tmp_path: Path) -> None:
    records = [
        _price_record("2025-12-30"),
        _price_record("2025-12-31"),
        _price_record("2026-01-02"),
    ]

    paths = write_price_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "fx=GBPUSD" / "year=2025" / "price.parquet",
        tmp_path / "fx=GBPUSD" / "year=2026" / "price.parquet",
    }

    year_2025 = pd.read_parquet(tmp_path / "fx=GBPUSD" / "year=2025" / "price.parquet")
    assert sorted(year_2025["date"]) == ["2025-12-30", "2025-12-31"]

    year_2026 = pd.read_parquet(tmp_path / "fx=GBPUSD" / "year=2026" / "price.parquet")
    assert year_2026.to_dict(orient="records") == [records[2]]


def test_write_price_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_price_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []
