"""Load the configured list of tickers to forecast dividends for.

A minimal, standalone loader for the same `{tickers: [...]}` YAML shape
`equicast-stock`/`equicast-etf` each already have their own copy of, kept
separate here (not imported from either) so `equicast-forecasting` doesn't
depend on an asset-class-specific package — it's handed `--config
packages/stock/config/stocks.dev.yaml` (or the ETF equivalent) directly,
same file, no copy needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def _ticker_of(entry: str | dict) -> str:
    """Each entry is a plain ticker string, or (stock/etf only) a
    `{ticker, isin}` mapping for a ticker with a manual ISIN override —
    forecasting has no use for isin, so it just takes the ticker."""
    return entry if isinstance(entry, str) else entry["ticker"]


def load_tickers(path: Path) -> list[str]:
    """Parse a YAML file of `{tickers: [...]}` into a list of ticker strings."""
    data = yaml.safe_load(path.read_text())
    return [_ticker_of(entry).upper() for entry in data["tickers"]]


def parse_tickers_json(payload: str) -> list[str]:
    """Parse a JSON array of ticker strings (or `{ticker, isin}` objects) into
    a list of ticker strings.

    Used to hand one chunk of a larger ticker list straight to the CLI (e.g. from a
    GitHub Actions matrix value) without mounting a config file into the container.
    """
    return [_ticker_of(entry).upper() for entry in json.loads(payload)]
