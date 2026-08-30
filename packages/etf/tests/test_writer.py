from pathlib import Path

import pandas as pd
from equicast_etf.writer import write_profile_parquet


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
