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
