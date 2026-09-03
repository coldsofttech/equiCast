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


def load_tickers(path: Path) -> list[str]:
    """Parse a YAML file of `{tickers: [...]}` into a list of ticker strings."""
    data = yaml.safe_load(path.read_text())
    return [ticker.upper() for ticker in data["tickers"]]


def parse_tickers_json(payload: str) -> list[str]:
    """Parse a JSON array of ticker strings into a list of ticker strings.

    Used to hand one chunk of a larger ticker list straight to the CLI (e.g. from a
    GitHub Actions matrix value) without mounting a config file into the container.
    """
    return [ticker.upper() for ticker in json.loads(payload)]
