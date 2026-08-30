"""Write extracted ETF data as Parquet, partitioned by ticker."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_profile_parquet(profile: dict[str, Any], output_dir: Path) -> Path:
    """Write `profile` to `<output_dir>/etf=<TICKER>/profile.parquet`."""
    directory = output_dir / f"etf={profile['ticker']}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.parquet"
    pd.DataFrame([profile]).to_parquet(path, index=False)
    return path


def write_price_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to one `<output_dir>/etf=<TICKER>/year=<YYYY>/price.parquet` per year."""
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    years = df["date"].str[:4]

    written = []
    for year, year_df in df.groupby(years):
        directory = output_dir / f"etf={ticker}" / f"year={year}"
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "price.parquet"
        year_df.to_parquet(path, index=False)
        written.append(path)
    return written


def write_dividend_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to one `<output_dir>/etf=<TICKER>/year=<YYYY>/dividend.parquet`
    per year."""
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    years = df["ex_dividend_date"].str[:4]

    written = []
    for year, year_df in df.groupby(years):
        directory = output_dir / f"etf={ticker}" / f"year={year}"
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "dividend.parquet"
        year_df.to_parquet(path, index=False)
        written.append(path)
    return written
