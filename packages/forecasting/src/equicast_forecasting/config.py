"""Load the configured list of tickers (dividend forecasting), FX pairs, or
benchmarks (price-band forecasting) to run against.

Minimal, standalone loaders for the same YAML shapes `equicast-stock`/
`equicast-etf`/`equicast-fx`/`equicast-benchmark` each already have their
own copy of, kept separate here (not imported from any of them) so
`equicast-forecasting` doesn't depend on an asset-class-specific package —
it's handed `--config packages/stock/config/stocks.dev.yaml` (or the
ETF/FX/benchmark equivalent) directly, same file, no copy needed.
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


@dataclass(frozen=True)
class BenchmarkRef:
    #: The S3 partition key this benchmark lands under
    #: (benchmark=<KEY>/...) - same field equicast_benchmark.config.
    #: Benchmark carries, and the same routing key benchmark_registry.py's
    #: schemas are keyed by.
    key: str
    #: The exact yfinance ticker to fetch, e.g. "^GSPC" - used as-is, not
    #: upper/lower-cased, same reasoning equicast_benchmark.config.
    #: Benchmark's own `symbol` field docstring gives.
    symbol: str


def _benchmarks_from_raw(raw: list[dict[str, Any]]) -> list[BenchmarkRef]:
    return [
        BenchmarkRef(key=benchmark["key"].upper(), symbol=benchmark["symbol"]) for benchmark in raw
    ]


def load_benchmarks(path: Path) -> list[BenchmarkRef]:
    """Parse a YAML file of `{benchmarks: [{key, symbol}, ...]}` (the same
    shape `equicast-benchmark`'s own config uses) into `BenchmarkRef`
    entries."""
    data = yaml.safe_load(path.read_text())
    return _benchmarks_from_raw(data["benchmarks"])


def parse_benchmarks_json(payload: str) -> list[BenchmarkRef]:
    """Parse a JSON array of `{"key": ..., "symbol": ...}` objects into
    `BenchmarkRef` entries.

    Used to hand one chunk of a larger benchmark list straight to the CLI
    (e.g. from a GitHub Actions matrix value) without mounting a config
    file into the container.
    """
    return _benchmarks_from_raw(json.loads(payload))
