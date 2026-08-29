"""Write extracted stock data as Parquet, partitioned by ticker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_profile_parquet(profile: dict[str, Any], output_dir: Path) -> Path:
    """Write `profile` to `<output_dir>/stock=<TICKER>/profile.parquet`.

    `ceos` is JSON-encoded to a plain string column here rather than written
    as a native list<struct> column: pandas/pyarrow round-trip that type
    fine, but common Parquet viewers (browser-based tools, editor
    extensions) are JS-based and just call `toString()` on the nested
    objects, rendering "[object Object]" instead of the actual data. A JSON
    string reads correctly in any viewer; consumers `json.loads()` it back.
    """
    record = {**profile, "ceos": json.dumps(profile["ceos"], ensure_ascii=False)}

    directory = output_dir / f"stock={profile['ticker']}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.parquet"
    pd.DataFrame([record]).to_parquet(path, index=False)
    return path
