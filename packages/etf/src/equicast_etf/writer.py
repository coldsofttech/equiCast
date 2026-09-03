"""Write extracted ETF data as Parquet, partitioned by ticker."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

#: Explicit schema for events.parquet, rather than letting pyarrow infer one
#: per year-file from whatever rows land in it: a ticker-year with only
#: splits (the only event type ETFs actually have — earnings/ratings are
#: always empty for them) leaves the earnings/rating-only columns
#: (eps_estimate, firm, ...) entirely null in that slice, and pyarrow would
#: otherwise infer a bare `null` type there. Pinning real types keeps every
#: year's file schema-compatible with every other, same as
#: `equicast-stock`'s `_EVENTS_SCHEMA` (kept identical here rather than
#: importing it, since `equicast_stock` isn't a dependency of
#: `equicast_etf`).
_EVENTS_SCHEMA = pa.schema(
    [
        ("ticker", pa.string()),
        ("event_type", pa.string()),
        ("date", pa.string()),
        ("eps_estimate", pa.float64()),
        ("reported_eps", pa.float64()),
        ("surprise_pct", pa.float64()),
        ("firm", pa.string()),
        ("from_grade", pa.string()),
        ("to_grade", pa.string()),
        ("action", pa.string()),
        ("ratio", pa.float64()),
        ("last_updated", pa.string()),
        ("source", pa.string()),
    ]
)


def write_profile_parquet(profile: dict[str, Any], output_dir: Path) -> Path:
    """Write `profile` to `<output_dir>/etf=<TICKER>/profile.parquet`."""
    directory = output_dir / f"etf={profile['ticker']}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "profile.parquet"
    pd.DataFrame([profile]).to_parquet(path, index=False)
    return path


def write_price_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to `<output_dir>/etf=<TICKER>/price/history.parquet` (every year
    before the current one) and/or `.../price/current.parquet` (the current year),
    instead of one file per year.

    `history.parquet` is only ever produced by a `--full-load` run — the default
    incremental fetch is `ytd`-only, so `records` never has pre-current-year rows to put
    in it — and is written wholesale from whatever `records` contains this call, not
    merged with any `history.parquet` already on disk: a second `--full-load` run
    replaces it rather than appending to it. `current.parquet` is rewritten by every run,
    full-load or incremental, since the current year always has *some* rows to write.
    This keeps the ticker's total price files at 2 regardless of how many years of
    history it has, rather than growing by one file per year.
    """
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    current_year = str(datetime.now(UTC).year)
    is_current_year = df["date"].str[:4] == current_year

    directory = output_dir / f"etf={ticker}" / "price"
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


def write_dividend_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to `<output_dir>/etf=<TICKER>/dividend/history.parquet` (every
    year before the current one) and/or `.../dividend/current.parquet` (the current
    year), instead of one file per year.

    Same split as `write_price_parquet` — see its docstring for the full reasoning.
    `history.parquet` is only ever produced by a `--full-load` run and is written
    wholesale from whatever `records` contains this call, not merged with any
    `history.parquet` already on disk. `current.parquet` is rewritten by every run that
    has any current-year ex-dividend rows to write (nothing at all is written for a
    ticker/year with no dividends, same as before this split).
    """
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    current_year = str(datetime.now(UTC).year)
    is_current_year = df["ex_dividend_date"].str[:4] == current_year

    directory = output_dir / f"etf={ticker}" / "dividend"
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


def write_metrics_parquet(metrics: dict[str, Any], ticker: str, output_dir: Path) -> Path:
    """Write `metrics` to `<output_dir>/etf=<TICKER>/metrics.parquet`.

    Unlike profile()/prices()/dividends(), MetricsClient is generic (keyed by
    a plain yfinance symbol, not a ticker), so the ticker identification is
    added here rather than already being present in `metrics`. Only
    `MetricsClient.metrics()`'s risk/performance fields are written here, not
    `.fundamentals()` — its valuation ratios (PE, EPS, margins, ...) are
    stock-only, mostly `None` or unreliable for ETFs, same as `equicast-fx`
    never calling it either.
    """
    record = {"ticker": ticker, **metrics}
    directory = output_dir / f"etf={ticker}"
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / "metrics.parquet"
    pd.DataFrame([record]).to_parquet(path, index=False)
    return path


def write_events_parquet(records: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    """Write `records` to `<output_dir>/etf=<TICKER>/events/history.parquet` (every year
    before the current one) and/or `.../events/current.parquet` (the current year
    onward), instead of one file per year.

    Like `equicast-stock`'s events.parquet, `records` mixes three distinct
    event types (earnings, rating changes, splits) tagged by an
    `event_type` column, so each file can hold everything that happened to
    the ticker in its range rather than splitting across separate files per
    type. In practice, ETF tickers only ever produce `"split"` rows here —
    `EventsClient` still fetches earnings dates and analyst ratings, but
    yfinance has none for a fund, so those two event types simply
    contribute no rows. Written with an explicit schema (`_EVENTS_SCHEMA`),
    not `DataFrame.to_parquet`'s default type inference — see
    `_EVENTS_SCHEMA`'s comment for why.

    Split the same way as `write_price_parquet`/`write_dividend_parquet` —
    see `write_price_parquet`'s docstring for the full reasoning — except
    `current.parquet` catches the current year *and any later one* (`>=`,
    not `==`), same as `equicast-stock`'s `write_events_parquet`: splits
    never carry a future date in practice, but this stays defensive against
    one the same way, rather than assuming today's zero-future-split
    observation always holds.
    """
    if not records:
        return []

    ticker = records[0]["ticker"]
    df = pd.DataFrame(records)
    current_year = str(datetime.now(UTC).year)
    is_current_or_later = df["date"].str[:4] >= current_year

    directory = output_dir / f"etf={ticker}" / "events"
    directory.mkdir(parents=True, exist_ok=True)

    written = []
    history_df = df[~is_current_or_later]
    if not history_df.empty:
        path = directory / "history.parquet"
        table = pa.Table.from_pandas(history_df, schema=_EVENTS_SCHEMA, preserve_index=False)
        pq.write_table(table, path)
        written.append(path)

    current_df = df[is_current_or_later]
    if not current_df.empty:
        path = directory / "current.parquet"
        table = pa.Table.from_pandas(current_df, schema=_EVENTS_SCHEMA, preserve_index=False)
        pq.write_table(table, path)
        written.append(path)
    return written
