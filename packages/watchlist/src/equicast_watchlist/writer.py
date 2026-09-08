"""Write a built system watchlist's entries as one Parquet file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_entries_parquet(
    watchlist_key: str, entries: list[dict[str, Any]], output_dir: Path
) -> Path:
    """Write `entries` to `<output_dir>/watchlist=<KEY>/entries.parquet` —
    one row per configured instrument, the whole watchlist rewritten
    wholesale each run (not merged with what's already published), since
    `entries` already reflects this run's complete, freshly-fetched list."""
    key = watchlist_key.upper()
    directory = output_dir / f"watchlist={key}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "entries.parquet"
    rows = [{"watchlist_key": key, **entry} for entry in entries]
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path
