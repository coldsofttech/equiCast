"""Write extracted FX data as Parquet, partitioned by pair."""

from __future__ import annotations

from datetime import UTC, datetime
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


def write_metrics_parquet(
    metrics: dict[str, Any], from_currency: str, to_currency: str, output_dir: Path
) -> Path:
    """Write `metrics` to `<output_dir>/fx=<FROM><TO>/metrics.parquet`.

    Unlike profile()/prices(), MetricsClient is generic (keyed by a plain
    yfinance symbol, not a currency pair), so the pair identification is
    added here rather than already being present in `metrics`.
    """
    record = {"from_currency": from_currency, "to_currency": to_currency, **metrics}
    directory = output_dir / f"fx={from_currency}{to_currency}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "metrics.parquet"
    pd.DataFrame([record]).to_parquet(path, index=False)
    return path


def write_price_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to `<output_dir>/fx=<FROM><TO>/price/history.parquet` (every year
    before the current one) and/or `.../price/current.parquet` (the current year),
    instead of one file per year.

    `history.parquet` is only ever produced by a `--full-load` run — the default
    incremental fetch is `ytd`-only, so `records` never has pre-current-year rows to put
    in it — and is written wholesale from whatever `records` contains this call, not
    merged with any `history.parquet` already on disk: a second `--full-load` run
    replaces it rather than appending to it. `current.parquet` is rewritten by every run,
    full-load or incremental, since the current year always has *some* rows to write.
    This keeps the pair's total price files at 2 regardless of how many years of history
    it has, rather than growing by one file per year.
    """
    if not records:
        return []

    pair_key = f"{records[0]['from_currency']}{records[0]['to_currency']}"
    df = pd.DataFrame(records)
    current_year = str(datetime.now(UTC).year)
    is_current_year = df["date"].str[:4] == current_year

    directory = output_dir / f"fx={pair_key}" / "price"
    directory.mkdir(parents=True, exist_ok=True)

    written = []
    history_df = df[~is_current_year]
    if not history_df.empty:
        path = directory / "history.parquet"
        history_df.to_parquet(path, index=False)
        written.append(path)

    current_df = df[is_current_year]
    if not current_df.empty:
        path = directory / "current.parquet"
        current_df.to_parquet(path, index=False)
        written.append(path)
    return written
