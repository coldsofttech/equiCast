"""Builds the five system-default watchlists' `holdings` live, at request
time, from each asset class's already-published `catalog/<asset_class>.
parquet` (see `equicast_core.catalog` — `ticker`/`name`/`currency`/
`current_price`, plus `cagr_1y`/`change_1w_pct`/`change_1m_pct` folded in
from that ticker's own `metrics.parquet` at catalog-build time). No
separate ingestion pipeline builds these — one catalog read per asset
class this run needs (at most 5, in practice 2-3 per system watchlist)
replaces what used to be a weekly `equicast-watchlist` batch job publishing
a pre-built `watchlist=<KEY>/entries.parquet` snapshot.

- `build_global_markets`: a hand-curated list of fx/future/benchmark
  tickers (`GLOBAL_MARKETS_ENTRIES` below), same membership
  `packages/watchlist/config/global_markets.prod.yaml` used to fetch fresh
  from yfinance every run — now just looked up in each of those three
  asset classes' own catalogs instead.
- `build_top_movers`: the whole stock/ETF universe (every `catalog/stock.
  parquet` + `catalog/etf.parquet` row), ranked by `cagr_1y` and sliced to
  the positive (winners) or negative (losers) side.
- `build_account_movers`: the same ranking, restricted to one caller's own
  account/pie holdings (deduplicated by ticker) instead of the whole
  universe — see `WatchlistListView.get`'s `account_pie_holdings`.

None of these mutate anything or call yfinance — pure reads of what the
five ingestion pipelines already publish, so there's nothing to schedule
and nothing that can go stale beyond however fresh that ticker's own last
ingestion run was.
"""

from __future__ import annotations

from typing import Any, Callable

#: The "Global Markets" watchlist's membership — every instrument it shows.
#: Same 16 futures + 4 fx pairs + 4 benchmarks
#: packages/watchlist/config/global_markets.prod.yaml used to list, migrated
#: here now that nothing fetches them fresh from yfinance for this purpose
#: (each is already ingested daily by fx/future/benchmark-ingestion.yml in
#: its own right — this list only decides which of those already-published
#: tickers Global Markets shows, not whether they get ingested at all).
#: `ticker` matches that asset class's own catalog `ticker` field exactly
#: (an fx pair's is `<FROM><TO>`, e.g. "EURUSD" — see equicast_fx.writer).
GLOBAL_MARKETS_ENTRIES: list[dict[str, str]] = [
    # --- Futures (every contract in packages/future/config/futures.*.yaml) ---
    {"asset_class": "future", "ticker": "GOLD", "name": "Gold"},
    {"asset_class": "future", "ticker": "SILVER", "name": "Silver"},
    {"asset_class": "future", "ticker": "PLATINUM", "name": "Platinum"},
    {"asset_class": "future", "ticker": "PALLADIUM", "name": "Palladium"},
    {"asset_class": "future", "ticker": "CRUDE_OIL_WTI", "name": "Crude Oil (WTI)"},
    {"asset_class": "future", "ticker": "BRENT_CRUDE", "name": "Brent Crude"},
    {"asset_class": "future", "ticker": "NATURAL_GAS", "name": "Natural Gas"},
    {"asset_class": "future", "ticker": "HEATING_OIL", "name": "Heating Oil"},
    {"asset_class": "future", "ticker": "COPPER", "name": "Copper"},
    {"asset_class": "future", "ticker": "ALUMINUM", "name": "Aluminum"},
    {"asset_class": "future", "ticker": "WHEAT", "name": "Wheat"},
    {"asset_class": "future", "ticker": "CORN", "name": "Corn"},
    {"asset_class": "future", "ticker": "SOYBEANS", "name": "Soybeans"},
    {"asset_class": "future", "ticker": "COFFEE", "name": "Coffee"},
    {"asset_class": "future", "ticker": "COTTON", "name": "Cotton"},
    {"asset_class": "future", "ticker": "SUGAR", "name": "Sugar"},
    # --- Currencies ---
    {"asset_class": "fx", "ticker": "EURUSD", "name": "EUR/USD"},
    {"asset_class": "fx", "ticker": "GBPUSD", "name": "GBP/USD"},
    {"asset_class": "fx", "ticker": "USDJPY", "name": "USD/JPY"},
    {"asset_class": "fx", "ticker": "USDCNY", "name": "USD/CNY"},
    # --- Benchmarks ---
    {"asset_class": "benchmark", "ticker": "SP500", "name": "S&P 500"},
    {"asset_class": "benchmark", "ticker": "FTSE100", "name": "FTSE 100"},
    {"asset_class": "benchmark", "ticker": "NASDAQ100", "name": "Nasdaq 100"},
    {"asset_class": "benchmark", "ticker": "VIX", "name": "VIX"},
]

#: The only two asset classes Top Winners/Top Losers and Your Top Winners/
#: Your Top Losers rank over — no fx/future/benchmark, matching Global
#: Markets' own scope being the curated list above instead.
MOVER_ASSET_CLASSES = ("stock", "etf")


def _catalog_row(
    market_data_client: Any, asset_class: str, ticker: str, catalogs: dict[str, dict[str, dict]]
) -> dict[str, Any] | None:
    if asset_class not in catalogs:
        catalogs[asset_class] = {
            row["ticker"]: row for row in market_data_client.get_catalog(asset_class)
        }
    return catalogs[asset_class].get(ticker)


def _display_row(
    asset_class: str, ticker: str, fallback_name: str, catalog_row: dict[str, Any] | None
) -> dict[str, Any]:
    row = catalog_row or {}
    return {
        "asset_class": asset_class,
        "ticker": ticker,
        "name": row.get("name") or fallback_name,
        "currency": row.get("currency"),
        "current_price": row.get("current_price"),
        "change_1w_pct": row.get("change_1w_pct"),
        "change_1m_pct": row.get("change_1m_pct"),
    }


def build_global_markets(market_data_client: Any) -> list[dict[str, Any]]:
    """Global Markets' entries, in `GLOBAL_MARKETS_ENTRIES`' own order —
    one catalog read per asset class it needs (fx/future/benchmark), not
    per entry. An entry whose ticker hasn't been published yet by its own
    ingestion pipeline still appears, with every field but `name` (falls
    back to the configured display name) and `asset_class`/`ticker`
    `None` — same "degrade gracefully, never drop a row" behavior the old
    equicast-watchlist snapshot had for a symbol yfinance had nothing for.
    """
    catalogs: dict[str, dict[str, dict]] = {}
    return [
        _display_row(
            entry["asset_class"],
            entry["ticker"],
            entry["name"],
            _catalog_row(market_data_client, entry["asset_class"], entry["ticker"], catalogs),
        )
        for entry in GLOBAL_MARKETS_ENTRIES
    ]


def stock_etf_catalog_rows(market_data_client: Any) -> list[dict[str, Any]]:
    """Every stock/ETF catalog row, tagged with its own asset_class —
    the shared universe both `build_top_movers` and `build_account_movers`
    rank over. Computed once per request by `WatchlistListView.get` and
    passed into both, rather than each re-reading the same two catalogs."""
    return [
        {**row, "asset_class": asset_class}
        for asset_class in MOVER_ASSET_CLASSES
        for row in market_data_client.get_catalog(asset_class)
    ]


def _rank(rows: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    """`rows` (each carrying its own `cagr_1y`) filtered to positive
    (winners) or negative (losers) CAGR and sorted highest/lowest first.
    A row with no `cagr_1y` yet (not enough history) is never eligible for
    either side."""
    if direction == "winners":
        candidates = [r for r in rows if r.get("cagr_1y") is not None and r["cagr_1y"] > 0]
        candidates.sort(key=lambda r: r["cagr_1y"], reverse=True)
    elif direction == "losers":
        candidates = [r for r in rows if r.get("cagr_1y") is not None and r["cagr_1y"] < 0]
        candidates.sort(key=lambda r: r["cagr_1y"])
    else:
        raise ValueError(f"Unknown direction '{direction}' — must be 'winners' or 'losers'.")
    return candidates


def build_top_movers(
    stock_etf_rows: list[dict[str, Any]], direction: str, limit: int
) -> list[dict[str, Any]]:
    """Top Winners/Top Losers: the `limit` highest/lowest `cagr_1y` rows
    across the whole stock/ETF universe, each carrying its own
    `change_1y_pct` (the CAGR it was ranked on, as a percent — same scale
    as `change_1w_pct`/`change_1m_pct`)."""
    selected = _rank(stock_etf_rows, direction)[:limit]
    return [
        {
            **_display_row(row["asset_class"], row["ticker"], row["ticker"], row),
            "change_1y_pct": round(row["cagr_1y"] * 100, 8),
        }
        for row in selected
    ]


def build_account_movers(
    stock_etf_rows: list[dict[str, Any]],
    direction: str,
    limit: int,
    account_pie_holdings: list[dict[str, Any]],
    enrich_holdings: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Your Top Winners/Your Top Losers: the caller's own real holdings
    (deduplicated by ticker — the same stock/ETF can appear in more than
    one account/pie) that rank on the winning/losing side of the same
    stock/ETF universe `build_top_movers` uses, enriched like a custom
    watchlist's holdings (`enrich_holdings`) plus each one's own
    `change_1y_pct`. Order follows the ranking, not `account_pie_holdings`'
    order. A held ticker with no catalog row yet, or no `cagr_1y`, is
    silently excluded rather than raising."""
    catalog_by_ticker = {row["ticker"]: row for row in stock_etf_rows}

    unique_holdings: dict[str, dict[str, Any]] = {}
    for holding in account_pie_holdings:
        if holding.get("asset_class") not in MOVER_ASSET_CLASSES:
            continue
        unique_holdings.setdefault(holding["ticker"], holding)

    ranked = _rank(
        [catalog_by_ticker[t] for t in unique_holdings if t in catalog_by_ticker], direction
    )[:limit]
    selected_holdings = [unique_holdings[row["ticker"]] for row in ranked]
    enriched_by_ticker = {h["ticker"]: h for h in enrich_holdings(selected_holdings)}
    cagr_by_ticker = {row["ticker"]: row["cagr_1y"] for row in ranked}

    result = []
    for row in ranked:
        holding = enriched_by_ticker.get(row["ticker"])
        if holding is None:
            continue
        result.append({**holding, "change_1y_pct": round(cagr_by_ticker[row["ticker"]] * 100, 8)})
    return result
