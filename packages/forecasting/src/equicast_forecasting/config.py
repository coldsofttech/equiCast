"""Load the configured list of tickers (dividend forecasting) or FX pairs
(price-band forecasting) to run against.

Minimal, standalone loaders for the same YAML shapes `equicast-stock`/
`equicast-etf`/`equicast-fx` each already have their own copy of, kept
separate here (not imported from any of them) so `equicast-forecasting`
doesn't depend on an asset-class-specific package — it's handed `--config
packages/stock/config/stocks.dev.yaml` (or the ETF/FX equivalent) directly,
same file, no copy needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class FxPairRef:
    from_currency: str
    to_currency: str


def _fx_pairs_from_raw(raw: list[dict[str, Any]]) -> list[FxPairRef]:
    return [
        FxPairRef(from_currency=pair["from"].upper(), to_currency=pair["to"].upper())
        for pair in raw
    ]


def load_fx_pairs(path: Path) -> list[FxPairRef]:
    """Parse a YAML file of `{pairs: [{from, to}, ...]}` (the same shape
    `equicast-fx`'s own config uses) into `FxPairRef` entries."""
    data = yaml.safe_load(path.read_text())
    return _fx_pairs_from_raw(data["pairs"])


def parse_fx_pairs_json(payload: str) -> list[FxPairRef]:
    """Parse a JSON array of `{"from": ..., "to": ...}` objects into
    `FxPairRef` entries.

    Used to hand one chunk of a larger pair list straight to the CLI (e.g. from a
    GitHub Actions matrix value) without mounting a config file into the container.
    """
    return _fx_pairs_from_raw(json.loads(payload))
