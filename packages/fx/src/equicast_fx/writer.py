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
