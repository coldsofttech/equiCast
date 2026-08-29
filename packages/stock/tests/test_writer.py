import json
from pathlib import Path

import pandas as pd
from equicast_stock.writer import write_profile_parquet


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
