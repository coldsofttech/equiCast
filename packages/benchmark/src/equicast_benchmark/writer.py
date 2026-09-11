"""Write extracted benchmark data as Parquet, partitioned by benchmark key."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def write_profile_parquet(profile: dict[str, Any], output_dir: Path) -> Path:
    """Write `profile` to `<output_dir>/benchmark=<KEY>/profile.parquet`."""
    directory = output_dir / f"benchmark={profile['key']}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.parquet"
    pd.DataFrame([profile]).to_parquet(path, index=False)
    return path


def write_metrics_parquet(metrics: dict[str, Any], key: str, output_dir: Path) -> Path:
    """Write `metrics` to `<output_dir>/benchmark=<KEY>/metrics.parquet`.

    Unlike profile()/prices(), MetricsClient is generic (keyed by a plain
    yfinance symbol, not a benchmark key), so the key is added here rather
    than already being present in `metrics`.
    """
    record = {"key": key, **metrics}
    directory = output_dir / f"benchmark={key}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "metrics.parquet"
    pd.DataFrame([record]).to_parquet(path, index=False)
    return path


def write_news_parquet(records: list[dict[str, Any]], key: str, output_dir: Path) -> list[Path]:
    """Write `records` to `<output_dir>/benchmark=<KEY>/news.parquet`.

    Unlike profile()/prices(), NewsClient is generic (keyed by a plain
    yfinance symbol, not a benchmark key), so `key` is added to each record
    here rather than already being present, same as `write_metrics_parquet`.
    A single flat file, not split into history/current — see
    `equicast_stock.writer.write_news_parquet`'s docstring for why.
    Omitted entirely when there's nothing to write.
    """
    if not records:
        return []

    tagged = [{"key": key, **record} for record in records]
    directory = output_dir / f"benchmark={key}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "news.parquet"
    pd.DataFrame(tagged).to_parquet(path, index=False)
    return [path]


def write_price_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to `<output_dir>/benchmark=<KEY>/price/history.parquet` (every year
    before the current one) and/or `.../price/current.parquet` (the current year),
    instead of one file per year.

    `history.parquet` is only ever produced by a `--full-load` run — the default
    incremental fetch is `ytd`-only, so `records` never has pre-current-year rows to put
    in it — and is written wholesale from whatever `records` contains this call, not
    merged with any `history.parquet` already on disk: a second `--full-load` run
    replaces it rather than appending to it. `current.parquet` is rewritten by every run,
    full-load or incremental, since the current year always has *some* rows to write.
    This keeps the benchmark's total price files at 2 regardless of how many years of
    history it has, rather than growing by one file per year.
    """
    if not records:
        return []

    key = records[0]["key"]
    df = pd.DataFrame(records)
    current_year = str(datetime.now(UTC).year)
    is_current_year = df["date"].str[:4] == current_year

    directory = output_dir / f"benchmark={key}" / "price"
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
