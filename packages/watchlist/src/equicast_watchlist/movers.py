"""Top Winners / Top Losers: rank every stock/ETF ticker by trailing 1-year
CAGR, then select the top (or bottom) of that ranking.

Split in two deliberately independent halves, matching the pipeline's own
step boundaries:

1. `compute_cagr_rankings` (step 1) reads every ticker out of the stock and
   ETF config YAMLs (the same ones equicast-stock/-etf ingest from — see
   their own `config/stocks.<env>.yaml`/`etfs.<env>.yaml`) and computes each
   one's trailing 1-year CAGR via `equicast_metrics.MetricsClient`, the same
   client equicast-stock/-etf/-fx/-future/-benchmark already use to publish
   `cagr_1y` in their own metrics.parquet. This step doesn't know or care
   which watchlist (if any) the result feeds — it's the same ranking a
   later user-specific "my top winners/losers" feature (ranking only a
   caller's own holdings) would need, just over the full universe instead.
2. `select_top` (steps 2/3) takes that ranking and slices out the winners
   or losers side of it.

`equicast_watchlist.cli`'s `--mode rank`/`--mode movers` are the CLI
surface over these two steps; write_rankings/load_rankings hand step 1's
result to steps 2 and 3 as a plain JSON file, computed once per pipeline
run rather than once per step (there is no other reason to reach back out
to yfinance for the same ranking twice in the same run).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from equicast_datafeed import DatafeedClient, round_value
from equicast_etf import load_etf_tickers
from equicast_metrics import MetricsClient
from equicast_stock import load_stock_tickers

from equicast_watchlist.config import WatchlistEntry

#: The only two asset classes Top Winners/Top Losers ranks over — unlike
#: Global Markets' explicit fx/future/benchmark entries, this is "the whole
#: investable universe", not a hand-curated list.
MOVER_ASSET_CLASSES = ("stock", "etf")

#: Ranking direction — "winners" keeps only positive CAGR (highest first),
#: "losers" keeps only negative CAGR (lowest, i.e. worst, first). See
#: `select_top`.
DIRECTIONS = ("winners", "losers")


@dataclass(frozen=True)
class TickerCagr:
    """One ticker's step-1 result: its trailing 1-year CAGR, as a fraction
    (e.g. 0.15 for +15%) — same scale as `MetricsClient.metrics()["cagr_1y"]`.
    `cagr_1y` is `None` when there isn't a full year of history yet (a
    recent listing) — such tickers are never eligible for either side of
    `select_top`."""

    asset_class: str
    ticker: str
    cagr_1y: float | None


def _universe(stock_config: Path, etf_config: Path) -> list[tuple[str, str]]:
    stocks = [("stock", t.ticker) for t in load_stock_tickers(stock_config)]
    etfs = [("etf", t.ticker) for t in load_etf_tickers(etf_config)]
    return [*stocks, *etfs]


def _rank_one(asset_class: str, ticker: str, datafeed: DatafeedClient) -> TickerCagr:
    cagr_1y = MetricsClient(ticker, datafeed=datafeed).metrics()["cagr_1y"]
    return TickerCagr(asset_class=asset_class, ticker=ticker, cagr_1y=cagr_1y)


def compute_cagr_rankings(
    stock_config: Path,
    etf_config: Path,
    datafeed: DatafeedClient,
    max_workers: int = 1,
) -> list[TickerCagr]:
    """Step 1: every stock/ETF ticker's trailing 1-year CAGR, in config order
    (stocks then ETFs) regardless of fetch completion order — same
    `ThreadPoolExecutor.map` ordering guarantee as `builder.build_entries`."""
    universe = _universe(stock_config, etf_config)
    if max_workers <= 1:
        return [_rank_one(asset_class, ticker, datafeed) for asset_class, ticker in universe]

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(
            executor.map(lambda pair: _rank_one(pair[0], pair[1], datafeed), universe)
        )


def write_rankings(rankings: list[TickerCagr], path: Path) -> Path:
    """Write step 1's result as a plain JSON array, for steps 2/3 to read
    back via `load_rankings` — not a watchlist itself, so not routed through
    `equicast_watchlist.writer`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in rankings]))
    return path


def load_rankings(path: Path) -> list[TickerCagr]:
    payload = json.loads(path.read_text())
    return [TickerCagr(**row) for row in payload]


def select_top(rankings: list[TickerCagr], direction: str, limit: int) -> list[TickerCagr]:
    """Steps 2/3: `direction == "winners"` keeps only tickers that actually
    gained over the trailing year (highest CAGR first); `"losers"` keeps
    only tickers that actually lost (lowest, i.e. most negative, CAGR
    first) — a mover watchlist should only ever contain instruments that
    moved the right way, not just whichever's numerically highest/lowest
    when the whole universe happens to be up or down. Tickers with no CAGR
    (not enough history yet) are always excluded. Returns at most `limit`
    entries — the ranking can come back shorter than `limit` if fewer than
    `limit` tickers qualify."""
    if direction == "winners":
        candidates = [r for r in rankings if r.cagr_1y is not None and r.cagr_1y > 0]
        candidates.sort(key=lambda r: r.cagr_1y, reverse=True)
    elif direction == "losers":
        candidates = [r for r in rankings if r.cagr_1y is not None and r.cagr_1y < 0]
        candidates.sort(key=lambda r: r.cagr_1y)
    else:
        raise ValueError(f"Unknown direction '{direction}' — must be one of {DIRECTIONS}.")
    return candidates[:limit]


def to_watchlist_entries(selected: list[TickerCagr]) -> list[WatchlistEntry]:
    """One `WatchlistEntry` per selected ticker, for `builder.build_entries`
    to fetch full profile/price data for — `name` falls back to the ticker
    itself (same as every other asset_class's config-provided `name`), a
    live profile's own name always wins once fetched."""
    return [
        WatchlistEntry(asset_class=r.asset_class, ticker=r.ticker, name=r.ticker)
        for r in selected
    ]


def merge_change_1y(
    rows: list[dict[str, object]], selected: list[TickerCagr]
) -> list[dict[str, object]]:
    """Attach each row's own `change_1y_pct` (its ranking CAGR, as a percent
    — same scale as `change_1w_pct`/`change_1m_pct`) in place, keyed off
    `ticker`. `built` rows and `selected` are always the same tickers in
    the same order (both derived from `to_watchlist_entries(selected)`), so
    this is really just a unit conversion, not a join — kept as one anyway
    so callers don't have to assume that ordering holds."""
    cagr_by_ticker = {r.ticker: r.cagr_1y for r in selected}
    for row in rows:
        cagr_1y = cagr_by_ticker.get(row["ticker"])  # type: ignore[arg-type]
        row["change_1y_pct"] = round_value(cagr_1y * 100 if cagr_1y is not None else None)
    return rows
