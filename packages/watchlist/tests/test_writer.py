import json
from pathlib import Path

import pandas as pd
from equicast_watchlist.writer import write_entries_parquet, write_failures_manifest


def _entry(ticker: str, **overrides) -> dict:
    row = {
        "asset_class": "future",
        "ticker": ticker,
        "symbol": f"{ticker}=F",
        "name": ticker.title(),
        "currency": "USD",
        "current_price": 100.0,
        "change_1w_pct": 1.5,
        "change_1m_pct": -2.0,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }
    row.update(overrides)
    return row


def test_write_entries_parquet_partitions_by_uppercased_key(tmp_path: Path) -> None:
    entries = [_entry("gold"), _entry("silver")]

    path = write_entries_parquet("global_markets", entries, tmp_path)

    assert path == tmp_path / "watchlist=GLOBAL_MARKETS" / "entries.parquet"
    result = pd.read_parquet(path)
    assert result.to_dict(orient="records") == [
        {"watchlist_key": "GLOBAL_MARKETS", **entries[0]},
        {"watchlist_key": "GLOBAL_MARKETS", **entries[1]},
    ]


def test_write_entries_parquet_writes_one_row_per_entry(tmp_path: Path) -> None:
    entries = [_entry(f"t{i}") for i in range(24)]

    path = write_entries_parquet("GLOBAL_MARKETS", entries, tmp_path)

    result = pd.read_parquet(path)
    assert len(result) == 24


def test_write_failures_manifest_writes_json(tmp_path: Path) -> None:
    failures = [{"ticker": "GOLD", "task": "profile", "error": "boom"}]

    path = write_failures_manifest(failures, tmp_path)

    assert path == tmp_path / "failures.json"
    assert json.loads(path.read_text(encoding="utf-8")) == failures


def test_write_failures_manifest_empty_failures_writes_nothing(tmp_path: Path) -> None:
    assert write_failures_manifest([], tmp_path) is None
    assert list(tmp_path.iterdir()) == []
