"""Write a built system watchlist's entries as one Parquet file."""

from __future__ import annotations

import json
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


def write_failures_manifest(failures: list[dict[str, str]], output_dir: Path) -> Path | None:
    """Write `failures` (each a `{"ticker", "task", "error"}` dict, one per
    entry that raised during this run - see `builder.build_entries`; the
    key is literally `"ticker"` even though this pipeline's items are
    watchlist entries, so every ingestion package's failures.json shares
    one schema) to `<output_dir>/failures.json`, so a partial failure can
    be reported without parsing container logs. Omitted entirely when
    `failures` is empty, same convention as `write_entries_parquet`'s
    sibling functions in equicast-stock/-etf/-fx/-benchmark/-future.
    """
    if not failures:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "failures.json"
    path.write_text(json.dumps(failures, indent=2), encoding="utf-8")
    return path
