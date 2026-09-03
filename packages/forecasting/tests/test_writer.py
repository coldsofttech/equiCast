from pathlib import Path

import pandas as pd
from equicast_forecasting.writer import write_dividend_forecast_parquet


def _record(ticker: str, ex_dividend_date: str, price: float) -> dict:
    return {
        "ticker": ticker,
        "currency": "USD",
        "ex_dividend_date": ex_dividend_date,
        "price": price,
        "dividend_frequency": "quarterly",
        "last_updated": "2026-08-30T09:00:02+00:00",
        "source": "equicast",
    }


def test_write_dividend_forecast_parquet_writes_stock_prefixed_path(tmp_path: Path) -> None:
    records = [_record("AAPL", "2026-11-10", 0.26), _record("AAPL", "2027-02-10", 0.27)]

    path = write_dividend_forecast_parquet(records, tmp_path, "stock")

    assert path == tmp_path / "stock=AAPL" / "forecasting" / "dividends.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == records


def test_write_dividend_forecast_parquet_writes_etf_prefixed_path(tmp_path: Path) -> None:
    records = [_record("VOO", "2026-11-10", 1.85)]

    path = write_dividend_forecast_parquet(records, tmp_path, "etf")

    assert path == tmp_path / "etf=VOO" / "forecasting" / "dividends.parquet"


def test_write_dividend_forecast_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_dividend_forecast_parquet([], tmp_path, "stock") is None
    assert list(tmp_path.iterdir()) == []
