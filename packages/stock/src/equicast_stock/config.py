"""Load the configured list of stock tickers to extract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class StockTicker:
    ticker: str
    isin: str | None = None
    tax_domicile: str | None = None

    @property
    def key(self) -> str:
        return self.ticker


def _tickers_from_raw(raw: list[str | dict]) -> list[StockTicker]:
    """Each entry is either a plain ticker string, or a `{ticker, isin,
    tax_domicile}` mapping for a ticker needing a manual override —
    `isin` for when yfinance's lookup missed it or returned a wrong/
    outdated value, `tax_domicile` for when the ticker's ISIN-derived
    domicile (see `equicast_stock.cli._derive_tax_domicile`) isn't right
    for this instrument (e.g. dual-listed, or domiciled somewhere other
    than its issuer's country) — either override always wins over the
    derived/fetched value, see `StockClient.profile`/`cli._profile_and_dividends_task`."""
    tickers = []
    for entry in raw:
        if isinstance(entry, str):
            tickers.append(StockTicker(ticker=entry.upper()))
        else:
            tickers.append(
                StockTicker(
                    ticker=entry["ticker"].upper(),
                    isin=entry.get("isin"),
                    tax_domicile=entry.get("tax_domicile"),
                )
            )
    return tickers


def load_stock_tickers(path: Path) -> list[StockTicker]:
    """Parse a YAML file of `{tickers: [...]}` into `StockTicker` entries."""
    data = yaml.safe_load(path.read_text())
    return _tickers_from_raw(data["tickers"])


def parse_stock_tickers_json(payload: str) -> list[StockTicker]:
    """Parse a JSON array of ticker strings (or `{ticker, isin}` objects, for
    an ISIN override) into `StockTicker` entries.

    Used to hand one chunk of a larger ticker list straight to the CLI (e.g. from a
    GitHub Actions matrix value) without mounting a config file into the container.
    """
    return _tickers_from_raw(json.loads(payload))
