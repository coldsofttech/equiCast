"""Load the configured list of benchmarks (market indices) to extract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Benchmark:
    #: S3 partition key this benchmark lands under (benchmark=<KEY>/...) —
    #: independent of yfinance's own symbol, so it stays stable even if a
    #: symbol's exact yfinance ticker ever changes.
    key: str
    #: The exact yfinance ticker to fetch, e.g. "^GSPC" — used as-is, not
    #: upper/lower-cased, since index symbols mix case and punctuation in
    #: ways a currency pair or stock ticker never does (e.g.
    #: "^990100-USD-STRD").
    symbol: str


def _benchmarks_from_raw(raw: list[dict[str, Any]]) -> list[Benchmark]:
    return [
        Benchmark(key=benchmark["key"].upper(), symbol=benchmark["symbol"])
        for benchmark in raw
    ]


def load_benchmarks(path: Path) -> list[Benchmark]:
    """Parse a YAML file of `{benchmarks: [{key, symbol}, ...]}` into `Benchmark` entries."""
    data = yaml.safe_load(path.read_text())
    return _benchmarks_from_raw(data["benchmarks"])


def parse_benchmarks_json(payload: str) -> list[Benchmark]:
    """Parse a JSON array of `{"key": ..., "symbol": ...}` objects into `Benchmark` entries.

    Used to hand one chunk of a larger benchmark list straight to the CLI
    (e.g. from a GitHub Actions matrix value) without mounting a config
    file into the container.
    """
    return _benchmarks_from_raw(json.loads(payload))
