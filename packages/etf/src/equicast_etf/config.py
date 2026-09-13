"""Load the configured list of ETF tickers to extract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ETFTicker:
    ticker: str
    isin: str | None = None

    @property
    def key(self) -> str:
        return self.ticker


def _tickers_from_raw(raw: list[str | dict]) -> list[ETFTicker]:
    """Each entry is either a plain ticker string, or a `{ticker, isin}`
    mapping for a ticker whose ISIN needs a manual override (yfinance's
    lookup missed it, or returned a wrong/outdated value) — the override
    always wins over the fetched value, see `ETFClient.profile`."""
    tickers = []
    for entry in raw:
        if isinstance(entry, str):
            tickers.append(ETFTicker(ticker=entry.upper()))
        else:
            tickers.append(ETFTicker(ticker=entry["ticker"].upper(), isin=entry.get("isin")))
    return tickers


def load_etf_tickers(path: Path) -> list[ETFTicker]:
    """Parse a YAML file of `{tickers: [...]}` into `ETFTicker` entries."""
    data = yaml.safe_load(path.read_text())
    return _tickers_from_raw(data["tickers"])


def parse_etf_tickers_json(payload: str) -> list[ETFTicker]:
    """Parse a JSON array of ticker strings (or `{ticker, isin}` objects, for
    an ISIN override) into `ETFTicker` entries.

    Used to hand one chunk of a larger ticker list straight to the CLI (e.g. from a
    GitHub Actions matrix value) without mounting a config file into the container.
    """
    return _tickers_from_raw(json.loads(payload))
