from pathlib import Path

import pandas as pd
from equicast_benchmark.writer import (
    write_metrics_parquet,
    write_price_parquet,
    write_profile_parquet,
)


def test_write_profile_parquet_partitions_by_key(tmp_path: Path) -> None:
    profile = {
        "key": "SP500",
        "symbol": "^GSPC",
        "name": "S&P 500",
        "exchange": "SNP",
        "currency": "USD",
        "region": "US",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }

    path = write_profile_parquet(profile, tmp_path)

    assert path == tmp_path / "benchmark=SP500" / "profile.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [profile]


def _price_record(date: str, **overrides) -> dict:
    record = {
        "key": "SP500",
        "symbol": "^GSPC",
        "date": date,
        "open": 6400.0,
        "high": 6420.0,
        "low": 6390.0,
        "close": 6410.0,
        "average": 6405.0,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def test_write_price_parquet_splits_into_history_and_current(tmp_path: Path) -> None:
    records = [
        _price_record("2025-12-30"),
        _price_record("2025-12-31"),
        _price_record("2026-01-02"),
    ]

    paths = write_price_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "benchmark=SP500" / "price" / "history.parquet",
        tmp_path / "benchmark=SP500" / "price" / "current.parquet",
    }

    history = pd.read_parquet(tmp_path / "benchmark=SP500" / "price" / "history.parquet")
    assert sorted(history["date"]) == ["2025-12-30", "2025-12-31"]

    current = pd.read_parquet(tmp_path / "benchmark=SP500" / "price" / "current.parquet")
    assert current.to_dict(orient="records") == [records[2]]


def test_write_price_parquet_current_year_only_writes_no_history_file(tmp_path: Path) -> None:
    records = [_price_record("2026-01-15")]

    paths = write_price_parquet(records, tmp_path)

    assert paths == [tmp_path / "benchmark=SP500" / "price" / "current.parquet"]
    assert not (tmp_path / "benchmark=SP500" / "price" / "history.parquet").exists()


def test_write_price_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_price_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_write_metrics_parquet_adds_key(tmp_path: Path) -> None:
    metrics = {
        "volatility": 0.083,
        "sharpe_ratio": 0.42,
        "max_drawdown": -0.061,
        "cagr_1y": 0.091,
        "cagr_2y": 0.08,
        "cagr_3y": 0.07,
        "cagr_5y": 0.09,
        "cagr_10y": 0.06,
        "last_updated": "2026-08-29T12:00:00+00:00",
        "source": "equicast",
    }

    path = write_metrics_parquet(metrics, "SP500", tmp_path)

    assert path == tmp_path / "benchmark=SP500" / "metrics.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [{"key": "SP500", **metrics}]
