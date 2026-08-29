"""Read and write market data as Parquet files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from equicast.config import settings


def parquet_path(ticker: str, data_dir: Path | None = None) -> Path:
    directory = data_dir or settings.data_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{ticker.upper()}.parquet"


def write_parquet(df: pd.DataFrame, ticker: str, data_dir: Path | None = None) -> Path:
    path = parquet_path(ticker, data_dir)
    df.to_parquet(path, index=False)
    return path


def read_parquet(ticker: str, data_dir: Path | None = None) -> pd.DataFrame:
    path = parquet_path(ticker, data_dir)
    return pd.read_parquet(path)
