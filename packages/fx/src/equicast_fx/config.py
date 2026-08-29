"""Load the configured list of FX pairs to extract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class FxPair:
    from_currency: str
    to_currency: str

    @property
    def key(self) -> str:
        return f"{self.from_currency}{self.to_currency}"


def _pairs_from_raw(raw: list[dict[str, Any]]) -> list[FxPair]:
    return [
        FxPair(from_currency=pair["from"].upper(), to_currency=pair["to"].upper())
        for pair in raw
    ]


def load_fx_pairs(path: Path) -> list[FxPair]:
    """Parse a YAML file of `{pairs: [{from, to}, ...]}` into `FxPair` entries."""
    data = yaml.safe_load(path.read_text())
    return _pairs_from_raw(data["pairs"])


def parse_fx_pairs_json(payload: str) -> list[FxPair]:
    """Parse a JSON array of `{"from": ..., "to": ...}` objects into `FxPair` entries.

    Used to hand one chunk of a larger pair list straight to the CLI (e.g. from a
    GitHub Actions matrix value) without mounting a config file into the container.
    """
    return _pairs_from_raw(json.loads(payload))
