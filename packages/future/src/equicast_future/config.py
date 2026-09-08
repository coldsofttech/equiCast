"""Load the configured list of futures contracts to extract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Future:
    #: S3 partition key this future lands under (future=<KEY>/...) —
    #: independent of yfinance's own symbol, so it stays stable even if a
    #: symbol's exact yfinance ticker ever changes.
    key: str
    #: The exact yfinance ticker to fetch, e.g. "GC=F" — used as-is, not
    #: upper/lower-cased, since futures symbols carry a fixed "=F" suffix
    #: that a currency pair or stock ticker never does.
    symbol: str


def _futures_from_raw(raw: list[dict[str, Any]]) -> list[Future]:
    return [Future(key=future["key"].upper(), symbol=future["symbol"]) for future in raw]


def load_futures(path: Path) -> list[Future]:
    """Parse a YAML file of `{futures: [{key, symbol}, ...]}` into `Future` entries."""
    data = yaml.safe_load(path.read_text())
    return _futures_from_raw(data["futures"])


def parse_futures_json(payload: str) -> list[Future]:
    """Parse a JSON array of `{"key": ..., "symbol": ...}` objects into `Future` entries.

    Used to hand one chunk of a larger futures list straight to the CLI
    (e.g. from a GitHub Actions matrix value) without mounting a config
    file into the container.
    """
    return _futures_from_raw(json.loads(payload))
