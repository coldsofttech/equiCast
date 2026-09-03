from pathlib import Path

import pandas as pd
from equicast_etf.writer import (
    write_dividend_parquet,
    write_events_parquet,
    write_metrics_parquet,
    write_price_parquet,
    write_profile_parquet,
)


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


def test_write_price_parquet_splits_into_history_and_current(tmp_path: Path) -> None:
    records = [
        _price_record("2025-12-30"),
        _price_record("2025-12-31"),
        _price_record("2026-01-02"),
    ]

    paths = write_price_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "etf=VOO" / "price" / "history.parquet",
        tmp_path / "etf=VOO" / "price" / "current.parquet",
    }

    history = pd.read_parquet(tmp_path / "etf=VOO" / "price" / "history.parquet")
    assert sorted(history["date"]) == ["2025-12-30", "2025-12-31"]

    current = pd.read_parquet(tmp_path / "etf=VOO" / "price" / "current.parquet")
    assert current.to_dict(orient="records") == [records[2]]


def test_write_price_parquet_current_year_only_writes_no_history_file(tmp_path: Path) -> None:
    records = [_price_record("2026-01-15")]

    paths = write_price_parquet(records, tmp_path)

    assert paths == [tmp_path / "etf=VOO" / "price" / "current.parquet"]
    assert not (tmp_path / "etf=VOO" / "price" / "history.parquet").exists()


def test_write_price_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_price_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def _dividend_record(ex_dividend_date: str, **overrides) -> dict:
    record = {
        "ticker": "VOO",
        "currency": "USD",
        "ex_dividend_date": ex_dividend_date,
        "price": 1.85,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def test_write_dividend_parquet_splits_into_history_and_current(tmp_path: Path) -> None:
    records = [
        _dividend_record("2025-11-10", price=1.80),
        _dividend_record("2026-02-10", price=1.85),
        _dividend_record("2026-05-12", price=1.90),
    ]

    paths = write_dividend_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "etf=VOO" / "dividend" / "history.parquet",
        tmp_path / "etf=VOO" / "dividend" / "current.parquet",
    }

    history = pd.read_parquet(tmp_path / "etf=VOO" / "dividend" / "history.parquet")
    assert history.to_dict(orient="records") == [records[0]]

    current = pd.read_parquet(tmp_path / "etf=VOO" / "dividend" / "current.parquet")
    assert sorted(current["ex_dividend_date"]) == ["2026-02-10", "2026-05-12"]


def test_write_dividend_parquet_current_year_only_writes_no_history_file(
    tmp_path: Path,
) -> None:
    records = [_dividend_record("2026-02-10")]

    paths = write_dividend_parquet(records, tmp_path)

    assert paths == [tmp_path / "etf=VOO" / "dividend" / "current.parquet"]
    assert not (tmp_path / "etf=VOO" / "dividend" / "history.parquet").exists()


def test_write_dividend_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_dividend_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def _event_record(event_type: str, date: str, **overrides) -> dict:
    record = {
        "ticker": "VOO",
        "event_type": event_type,
        "date": date,
        "eps_estimate": None,
        "reported_eps": None,
        "surprise_pct": None,
        "firm": None,
        "from_grade": None,
        "to_grade": None,
        "action": None,
        "ratio": None,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def test_write_events_parquet_splits_into_history_and_current(tmp_path: Path) -> None:
    records = [
        _event_record("split", "2000-03-20", ratio=2.0),
        _event_record("split", "2026-06-09", ratio=4.0),
    ]

    paths = write_events_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "etf=VOO" / "events" / "history.parquet",
        tmp_path / "etf=VOO" / "events" / "current.parquet",
    }

    # Read back via the pyarrow dtype backend, not plain pd.read_parquet's
    # default numpy backend: a fully-null column (e.g. `firm`, since ETFs
    # only ever produce "split" rows here) round-trips as float NaN under
    # the numpy backend regardless of its declared type - a pyarrow/pandas
    # interop quirk, not something _EVENTS_SCHEMA's pinning is meant to fix
    # (see its comment). The pyarrow backend preserves real None, which is
    # what this test cares about.
    current = pd.read_parquet(
        tmp_path / "etf=VOO" / "events" / "current.parquet", dtype_backend="pyarrow"
    )
    assert current.to_dict(orient="records") == [records[1]]

    # Plain pd.read_parquet (no dtype_backend override) is the more common
    # call, so also confirm the documented NaN-not-None quirk actually
    # happens for an all-null column, rather than just asserting it away.
    history_default = pd.read_parquet(tmp_path / "etf=VOO" / "events" / "history.parquet")
    assert pd.isna(history_default["firm"].iloc[0])


def test_write_events_parquet_current_year_or_later_only_writes_no_history_file(
    tmp_path: Path,
) -> None:
    records = [_event_record("split", "2026-06-09", ratio=4.0)]

    paths = write_events_parquet(records, tmp_path)

    assert paths == [tmp_path / "etf=VOO" / "events" / "current.parquet"]
    assert not (tmp_path / "etf=VOO" / "events" / "history.parquet").exists()


def test_write_events_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_events_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_write_metrics_parquet_adds_ticker_identification(tmp_path: Path) -> None:
    metrics = {
        "volatility": 0.13,
        "sharpe_ratio": 1.55,
        "max_drawdown": -0.09,
        "cagr_1y": 0.2,
        "cagr_2y": 0.19,
        "cagr_3y": 0.22,
        "cagr_5y": 0.13,
        "cagr_10y": 0.15,
        "last_updated": "2026-08-30T09:00:00+00:00",
        "source": "equicast",
    }

    path = write_metrics_parquet(metrics, "VOO", tmp_path)

    assert path == tmp_path / "etf=VOO" / "metrics.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [{"ticker": "VOO", **metrics}]
