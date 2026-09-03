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
