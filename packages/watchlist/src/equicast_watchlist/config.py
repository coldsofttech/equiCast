"""Load the configured list of instruments (fx pairs, futures, benchmarks)
that make up one system watchlist snapshot (e.g. Global Markets) — see
config/global_markets.yaml for the exact per-`asset_class` shape."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

#: Every asset_class a watchlist entry's config row may declare — each maps
#: to one of equicast-fx/-future/-benchmark's own Client classes, see
#: equicast_watchlist.builder's dispatch.
ASSET_CLASSES = ("fx", "future", "benchmark")


@dataclass(frozen=True)
class WatchlistEntry:
    #: Which Client class builds this entry — "fx" (equicast_fx.FXClient),
    #: "future" (equicast_future.FutureClient), or "benchmark"
    #: (equicast_benchmark.BenchmarkClient).
    asset_class: str
    #: Display/output ticker — `from_currency+to_currency` for fx (derived
    #: below, matching FXClient's own `symbol` derivation minus the "=X"
    #: suffix), or that entry's own `key` for future/benchmark.
    ticker: str
    #: Fallback display name (e.g. "EUR/USD", "Gold", "S&P 500"), used only
    #: when the live yfinance fetch doesn't return one at all (down/rate-
    #: limited) — a live profile's own name always wins once fetched.
    name: str
    #: Set only for asset_class == "fx" — FXClient(from_currency, to_currency).
    from_currency: str | None = None
    to_currency: str | None = None
    #: Set only for asset_class in ("future", "benchmark") —
    #: FutureClient/BenchmarkClient(key, symbol).
    key: str | None = None
    symbol: str | None = None


def _entry_from_raw(raw: dict[str, Any]) -> WatchlistEntry:
    asset_class = raw["asset_class"]
    if asset_class == "fx":
        from_currency = raw["from"].upper()
        to_currency = raw["to"].upper()
        return WatchlistEntry(
            asset_class="fx",
            ticker=f"{from_currency}{to_currency}",
            name=raw["name"],
            from_currency=from_currency,
            to_currency=to_currency,
        )
    if asset_class in ("future", "benchmark"):
        key = raw["key"].upper()
        return WatchlistEntry(
            asset_class=asset_class,
            ticker=key,
            name=raw["name"],
            key=key,
            symbol=raw["symbol"],
        )
    raise ValueError(
        f"Unknown asset_class '{asset_class}' in watchlist config — must be one of {ASSET_CLASSES}."
    )


def load_watchlist_entries(path: Path) -> list[WatchlistEntry]:
    """Parse a YAML file of `{entries: [...]}` into `WatchlistEntry` objects."""
    data = yaml.safe_load(path.read_text())
    return [_entry_from_raw(raw) for raw in data["entries"]]
