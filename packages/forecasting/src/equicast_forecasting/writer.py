"""Write projected dividend Parquet, partitioned by asset class and ticker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_dividend_forecast_parquet(
    records: list[dict[str, Any]], output_dir: Path, asset_class: str
) -> Path | None:
    """Write `records` (as returned by `equicast_forecasting.dividends()`) to
    `<output_dir>/<asset_class>=<TICKER>/forecasting/dividends.parquet`.

    Returns `None` (writes nothing) for `records == []` — `dividends()`
    already returns `[]` for a ticker with no dependable cadence to
    forecast (an "irregular"/"not_applicable" payer), so there's nothing
    meaningful to write for it. Rewritten wholesale on every run — unlike
    price/dividend/events, this is always a full recomputation from that
    run's freshly-fetched dividend history, not an accumulating history, so
    there's no history.parquet/current.parquet split here.
    """
    if not records:
        return None

    ticker = records[0]["ticker"]
    directory = output_dir / f"{asset_class}={ticker}" / "forecasting"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "dividends.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path


def write_stock_price_bands_parquet(records: list[dict[str, Any]], output_dir: Path) -> Path | None:
    """Write `records` (as returned by `equicast_forecasting.stock_forecast.
    stock_price_bands()`) to `<output_dir>/stock=<TICKER>/forecasting/
    price_bands.parquet` — same layout convention as `write_dividend_
    forecast_parquet`/`write_fx_price_bands_parquet`.

    Returns `None` (writes nothing) for `records == []` — `stock_price_
    bands()` already returns `[]` for a ticker with too little price
    history to forecast from. Rewritten wholesale on every run, same as
    every other forecasting writer — a full recomputation from that run's
    freshly-fetched price/fundamentals data, not an accumulating history.
    """
    if not records:
        return None

    ticker = records[0]["ticker"]
    directory = output_dir / f"stock={ticker}" / "forecasting"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "price_bands.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path


def write_etf_price_bands_parquet(records: list[dict[str, Any]], output_dir: Path) -> Path | None:
    """Write `records` (as returned by `equicast_forecasting.etf_forecast.
    etf_price_bands()`) to `<output_dir>/etf=<TICKER>/forecasting/
    price_bands.parquet` — same layout convention as `write_stock_price_
    bands_parquet`.

    Returns `None` (writes nothing) for `records == []` — `etf_price_
    bands()` already returns `[]` for a ticker with too little price
    history to forecast from. Rewritten wholesale on every run, same as
    every other forecasting writer — a full recomputation from that run's
    freshly-fetched price/signal data, not an accumulating history.
    """
    if not records:
        return None

    ticker = records[0]["ticker"]
    directory = output_dir / f"etf={ticker}" / "forecasting"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "price_bands.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path


def write_benchmark_price_bands_parquet(
    records: list[dict[str, Any]], output_dir: Path
) -> Path | None:
    """Write `records` (as returned by `equicast_forecasting.
    benchmark_forecast.benchmark_price_bands()`) to
    `<output_dir>/benchmark=<KEY>/forecasting/price_bands.parquet` — same
    `benchmark=<KEY>` partition convention `equicast_benchmark.writer` uses.

    Returns `None` (writes nothing) for `records == []` — `benchmark_
    price_bands()` already returns `[]` for a benchmark with too little
    price history to forecast from. Rewritten wholesale on every run, same
    as every other forecasting writer — a full recomputation from that
    run's freshly-fetched price history, not an accumulating history.
    """
    if not records:
        return None

    key = records[0]["key"]
    directory = output_dir / f"benchmark={key}" / "forecasting"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "price_bands.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path


def write_future_price_bands_parquet(
    records: list[dict[str, Any]], output_dir: Path
) -> Path | None:
    """Write `records` (as returned by `equicast_forecasting.
    future_forecast.future_price_bands()`) to
    `<output_dir>/future=<KEY>/forecasting/price_bands.parquet` — same
    `future=<KEY>` partition convention `equicast_future.writer` uses.

    Returns `None` (writes nothing) for `records == []` — `future_price_
    bands()` already returns `[]` for a future with too little price
    history to forecast from. Rewritten wholesale on every run, same as
    every other forecasting writer — a full recomputation from that run's
    freshly-fetched price history, not an accumulating history.
    """
    if not records:
        return None

    key = records[0]["key"]
    directory = output_dir / f"future={key}" / "forecasting"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "price_bands.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path


def write_fx_price_bands_parquet(records: list[dict[str, Any]], output_dir: Path) -> Path | None:
    """Write `records` (as returned by `equicast_forecasting.fx_forecast.
    fx_price_bands()`) to `<output_dir>/fx=<FROM><TO>/forecasting/
    price_bands.parquet` — same `fx=<FROM><TO>` pair-key convention
    `equicast_fx.writer` uses.

    Returns `None` (writes nothing) for `records == []` — `fx_price_bands()`
    already returns `[]` for fewer than 2 price records to forecast from.
    Rewritten wholesale on every run, same as `write_dividend_forecast_
    parquet` — a full recomputation from that run's freshly-fetched price
    history, not an accumulating history, so there's no history.parquet/
    current.parquet split here either.
    """
    if not records:
        return None

    pair_key = f"{records[0]['from_currency']}{records[0]['to_currency']}"
    directory = output_dir / f"fx={pair_key}" / "forecasting"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "price_bands.parquet"
    pd.DataFrame(records).to_parquet(path, index=False)
    return path
