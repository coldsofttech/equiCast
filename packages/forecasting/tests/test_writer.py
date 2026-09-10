from pathlib import Path

import pandas as pd
from equicast_forecasting.writer import (
    write_benchmark_price_bands_parquet,
    write_dividend_forecast_parquet,
    write_etf_price_bands_parquet,
    write_fx_price_bands_parquet,
    write_stock_price_bands_parquet,
)


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


def _band_record(date: str, **overrides) -> dict:
    record = {
        "from_currency": "GBP",
        "to_currency": "USD",
        "date": date,
        "p10": 1.20,
        "p50": 1.32,
        "p90": 1.45,
        "regime": "short",
        "volatility_model": "ewma",
        "last_updated": "2026-08-30T09:00:02+00:00",
        "source": "equicast",
    }
    record.update(overrides)
    return record


def test_write_fx_price_bands_parquet_writes_pair_prefixed_path(tmp_path: Path) -> None:
    records = [_band_record("2026-09-01"), _band_record("2026-09-02")]

    path = write_fx_price_bands_parquet(records, tmp_path)

    assert path == tmp_path / "fx=GBPUSD" / "forecasting" / "price_bands.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == records


def test_write_fx_price_bands_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_fx_price_bands_parquet([], tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def _stock_band_record(date: str, **overrides) -> dict:
    record = {
        "ticker": "AAPL",
        "sector": "Technology",
        "sub_sector": "technology",
        "date": date,
        "p10": 180.0,
        "p50": 200.0,
        "p90": 220.0,
        "regime": "short",
        "volatility_model": "garch",
        "valuation_multiple_family": "pe",
        "valuation_multiple": 30.0,
        "valuation_zscore": 0.5,
        "revenue_cagr": 0.1,
        "profit_margin_trend": 0.02,
        "rd_to_revenue": 0.08,
        "short_interest_ratio": 0.01,
        "last_updated": "2026-08-30T09:00:02+00:00",
        "source": "equicast",
    }
    record.update(overrides)
    return record


def test_write_stock_price_bands_parquet_writes_ticker_prefixed_path(tmp_path: Path) -> None:
    records = [_stock_band_record("2026-09-01"), _stock_band_record("2026-09-02")]

    path = write_stock_price_bands_parquet(records, tmp_path)

    assert path == tmp_path / "stock=AAPL" / "forecasting" / "price_bands.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == records


def test_write_stock_price_bands_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_stock_price_bands_parquet([], tmp_path) is None


def _etf_band_record(date: str, **overrides: object) -> dict:
    record = {
        "ticker": "VOO",
        "etf_type": "Broad/S&P",
        "etf_type_key": "broad_sp",
        "date": date,
        "p10": 480.0,
        "p50": 500.0,
        "p90": 520.0,
        "regime": "short",
        "volatility_model": "garch",
        "expense_ratio": 0.0003,
        "dividend_yield": 0.013,
        "nav_premium_discount": 0.0001,
        "aggregate_pe": 27.5,
        "last_updated": "2026-08-30T09:00:02+00:00",
        "source": "equicast",
    }
    record.update(overrides)
    return record


def test_write_etf_price_bands_parquet_writes_ticker_prefixed_path(tmp_path: Path) -> None:
    records = [_etf_band_record("2026-09-01"), _etf_band_record("2026-09-02")]

    path = write_etf_price_bands_parquet(records, tmp_path)

    assert path == tmp_path / "etf=VOO" / "forecasting" / "price_bands.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == records


def test_write_etf_price_bands_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_etf_price_bands_parquet([], tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def _benchmark_band_record(date: str, **overrides: object) -> dict:
    record = {
        "key": "SP500",
        "benchmark": "S&P 500",
        "currency_sensitivity": "low",
        "date": date,
        "p10": 4300.0,
        "p50": 4500.0,
        "p90": 4700.0,
        "regime": "short",
        "volatility_model": "garch",
        "cape_zscore": None,
        "last_updated": "2026-08-30T09:00:02+00:00",
        "source": "equicast",
    }
    record.update(overrides)
    return record


def test_write_benchmark_price_bands_parquet_writes_key_prefixed_path(tmp_path: Path) -> None:
    records = [_benchmark_band_record("2026-09-01"), _benchmark_band_record("2026-09-02")]

    path = write_benchmark_price_bands_parquet(records, tmp_path)

    assert path == tmp_path / "benchmark=SP500" / "forecasting" / "price_bands.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == records


def test_write_benchmark_price_bands_parquet_empty_records_writes_nothing(tmp_path: Path) -> None:
    assert write_benchmark_price_bands_parquet([], tmp_path) is None
