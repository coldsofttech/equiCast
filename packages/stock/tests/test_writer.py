import json
from pathlib import Path

import pandas as pd
from equicast_stock.writer import (
    write_dividend_parquet,
    write_events_parquet,
    write_metrics_parquet,
    write_price_parquet,
    write_profile_parquet,
)


def test_write_profile_parquet_partitions_by_ticker(tmp_path: Path) -> None:
    profile = {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "quote_type": "EQUITY",
        "exchange": "NMS",
        "currency": "USD",
        "description": "Apple Inc. designs, manufactures, and markets smartphones.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "website": "https://www.apple.com",
        "beta": 1.2,
        "payout_ratio": 0.15,
        "dividend_rate": 1.0,
        "dividend_yield": 0.005,
        "market_cap": 3000000000000,
        "volume": 50000000,
        "day_open": 227.5,
        "day_high": 229.1,
        "day_low": 226.8,
        "day_close": 228.5,
        "day_average": 227.95,
        "year_open": 180.0,
        "year_high": 260.1,
        "year_low": 164.08,
        "year_close": 228.5,
        "year_average": 212.09,
        "moving_average_50_days": 220.45,
        "moving_average_200_days": 200.12,
        "address": "One Apple Park Way, Cupertino, CA 95014",
        "country": "United States",
        "region": "North America",
        "full_time_employees": 164000,
        "ceos": [{"name": "Timothy D. Cook", "role": "CEO & Director"}],
        "ipo_date": "1980-12-12T14:30:00+00:00",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }

    path = write_profile_parquet(profile, tmp_path)

    assert path == tmp_path / "stock=AAPL" / "profile.parquet"
    result = pd.read_parquet(path)
    records = result.to_dict(orient="records")
    # ceos is JSON-encoded to a plain string in the Parquet file (see
    # write_profile_parquet's docstring) rather than a native list<struct>
    # column, so viewers show readable text instead of "[object Object]".
    expected = {**profile, "ceos": json.dumps(profile["ceos"], ensure_ascii=False)}
    assert records == [expected]


def test_write_profile_parquet_json_encodes_ceos_with_non_ascii_names(tmp_path: Path) -> None:
    profile = {"ticker": "AAPL", "ceos": [{"name": "François Dubois", "role": "CEO"}]}

    path = write_profile_parquet(profile, tmp_path)

    result = pd.read_parquet(path)
    assert result.to_dict(orient="records")[0]["ceos"] == json.dumps(
        profile["ceos"], ensure_ascii=False
    )
    assert "François" in result.to_dict(orient="records")[0]["ceos"]


def _price_record(date: str, **overrides) -> dict:
    record = {
        "ticker": "AAPL",
        "currency": "USD",
        "date": date,
        "open": 225.30,
        "high": 227.32,
        "low": 224.29,
        "close": 226.31,
        "average": 225.80,
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
        tmp_path / "stock=AAPL" / "price" / "history.parquet",
        tmp_path / "stock=AAPL" / "price" / "current.parquet",
    }

    history = pd.read_parquet(tmp_path / "stock=AAPL" / "price" / "history.parquet")
    assert sorted(history["date"]) == ["2025-12-30", "2025-12-31"]

    current = pd.read_parquet(tmp_path / "stock=AAPL" / "price" / "current.parquet")
    assert current.to_dict(orient="records") == [records[2]]


def test_write_price_parquet_current_year_only_writes_no_history_file(tmp_path: Path) -> None:
    records = [_price_record("2026-01-15")]

    paths = write_price_parquet(records, tmp_path)

    assert paths == [tmp_path / "stock=AAPL" / "price" / "current.parquet"]
    assert not (tmp_path / "stock=AAPL" / "price" / "history.parquet").exists()


def test_write_price_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_price_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def _dividend_record(ex_dividend_date: str, **overrides) -> dict:
    record = {
        "ticker": "AAPL",
        "currency": "USD",
        "ex_dividend_date": ex_dividend_date,
        "price": 0.26,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    record.update(overrides)
    return record


def test_write_dividend_parquet_splits_into_history_and_current(tmp_path: Path) -> None:
    records = [
        _dividend_record("2025-11-10", price=0.25),
        _dividend_record("2026-02-10", price=0.26),
        _dividend_record("2026-05-12", price=0.27),
    ]

    paths = write_dividend_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "stock=AAPL" / "dividend" / "history.parquet",
        tmp_path / "stock=AAPL" / "dividend" / "current.parquet",
    }

    history = pd.read_parquet(tmp_path / "stock=AAPL" / "dividend" / "history.parquet")
    assert history.to_dict(orient="records") == [records[0]]

    current = pd.read_parquet(tmp_path / "stock=AAPL" / "dividend" / "current.parquet")
    assert sorted(current["ex_dividend_date"]) == ["2026-02-10", "2026-05-12"]


def test_write_dividend_parquet_current_year_only_writes_no_history_file(
    tmp_path: Path,
) -> None:
    records = [_dividend_record("2026-02-10")]

    paths = write_dividend_parquet(records, tmp_path)

    assert paths == [tmp_path / "stock=AAPL" / "dividend" / "current.parquet"]
    assert not (tmp_path / "stock=AAPL" / "dividend" / "history.parquet").exists()


def test_write_dividend_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_dividend_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def _event_record(event_type: str, date: str, **overrides) -> dict:
    record = {
        "ticker": "AAPL",
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
        _event_record("earnings", "2025-10-30", reported_eps=1.5, surprise_pct=2.0),
        _event_record("rating", "2026-03-01", firm="Morgan Stanley", action="up"),
        _event_record("split", "2026-06-09", ratio=4.0),
    ]

    paths = write_events_parquet(records, tmp_path)

    assert set(paths) == {
        tmp_path / "stock=AAPL" / "events" / "history.parquet",
        tmp_path / "stock=AAPL" / "events" / "current.parquet",
    }

    # Read back via the pyarrow dtype backend, not plain pd.read_parquet's
    # default numpy backend: a fully-null column in a given file (e.g.
    # `firm` in history.parquet, since 2025 only has an earnings event)
    # round-trips as float NaN under the numpy backend regardless of its
    # declared type - a pyarrow/pandas interop quirk, not something
    # _EVENTS_SCHEMA's pinning is meant to fix (see its comment). The
    # pyarrow backend preserves real None, which is what this test cares
    # about.
    history = pd.read_parquet(
        tmp_path / "stock=AAPL" / "events" / "history.parquet", dtype_backend="pyarrow"
    )
    assert history.to_dict(orient="records") == [records[0]]

    current = pd.read_parquet(
        tmp_path / "stock=AAPL" / "events" / "current.parquet", dtype_backend="pyarrow"
    )
    assert sorted(current["event_type"]) == ["rating", "split"]
    rating_row = current[current["event_type"] == "rating"].to_dict(orient="records")[0]
    assert rating_row["eps_estimate"] is None
    assert rating_row["firm"] == "Morgan Stanley"

    # Plain pd.read_parquet (no dtype_backend override) is the more common
    # call, so also confirm the documented NaN-not-None quirk actually
    # happens for an all-null column, rather than just asserting it away.
    history_default = pd.read_parquet(tmp_path / "stock=AAPL" / "events" / "history.parquet")
    assert pd.isna(history_default["firm"].iloc[0])


def test_write_events_parquet_current_year_or_later_only_writes_no_history_file(
    tmp_path: Path,
) -> None:
    records = [
        _event_record("rating", "2026-03-01", firm="Morgan Stanley", action="up"),
        _event_record("earnings", "2027-01-15", eps_estimate=2.1),
    ]

    paths = write_events_parquet(records, tmp_path)

    assert paths == [tmp_path / "stock=AAPL" / "events" / "current.parquet"]
    assert not (tmp_path / "stock=AAPL" / "events" / "history.parquet").exists()


def test_write_events_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_events_parquet([], tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_write_metrics_parquet_adds_ticker_identification(tmp_path: Path) -> None:
    metrics = {
        "volatility": 0.24,
        "sharpe_ratio": 0.81,
        "max_drawdown": -0.18,
        "cagr_1y": 0.21,
        "cagr_2y": 0.15,
        "cagr_3y": 0.12,
        "cagr_5y": 0.19,
        "cagr_10y": 0.22,
        "trailing_pe": 30.1,
        "forward_pe": 27.4,
        "trailing_eps": 6.13,
        "forward_eps": 6.75,
        "peg": 2.05,
        "price_to_book": 45.2,
        "price_to_sales": 8.1,
        "ev_ebitda": 21.3,
        "gross_margin": 0.462,
        "operating_margin": 0.312,
        "profit_margin": 0.24,
        "return_on_equity": 1.52,
        "return_on_assets": 0.29,
        "debt_to_equity": 148.6,
        "free_cash_flow_per_share": 6.42,
        "last_updated": "2026-08-30T09:00:00+00:00",
        "source": "yfinance",
    }

    path = write_metrics_parquet(metrics, "AAPL", tmp_path)

    assert path == tmp_path / "stock=AAPL" / "metrics.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [{"ticker": "AAPL", **metrics}]
