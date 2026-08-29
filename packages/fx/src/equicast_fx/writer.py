"""Write extracted FX data as Parquet, partitioned by pair."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_profile_parquet(profile: dict[str, Any], output_dir: Path) -> Path:
    """Write `profile` to `<output_dir>/fx=<FROM><TO>/profile.parquet`."""
    pair_key = f"{profile['from_currency']}{profile['to_currency']}"
    directory = output_dir / f"fx={pair_key}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.parquet"
    pd.DataFrame([profile]).to_parquet(path, index=False)
    return path


def write_price_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to one `<output_dir>/fx=<FROM><TO>/year=<YYYY>/price.parquet` per year."""
    if not records:
        return []

    pair_key = f"{records[0]['from_currency']}{records[0]['to_currency']}"
    df = pd.DataFrame(records)
    years = df["date"].str[:4]

    written = []
    for year, year_df in df.groupby(years):
        directory = output_dir / f"fx={pair_key}" / f"year={year}"
        directory.mkdir(parents=True, exist_ok=True)

        path = directory / "price.parquet"
        year_df.to_parquet(path, index=False)
        written.append(path)
    return written
