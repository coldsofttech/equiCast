"""Pure-logic tests for watchlists.system_watchlists — no Django/S3
involved, just `MarketDataClient`-shaped mocks, same style as
equicast_api/test_lambda_handler.py's plain test functions (nothing here
touches the ORM or settings, so a TestCase would only add overhead)."""

from unittest.mock import MagicMock

from watchlists.system_watchlists import (
    GLOBAL_MARKETS_ENTRIES,
    build_account_movers,
    build_global_markets,
    build_top_movers,
    stock_etf_catalog_rows,
)


def _catalog_row(ticker: str, **overrides) -> dict:
    return {
        "ticker": ticker,
        "name": f"{ticker} Inc.",
        "type": overrides.pop("type", "stock"),
        "current_price": 100.0,
        "currency": "USD",
        "cagr_1y": None,
        "change_1w_pct": None,
        "change_1m_pct": None,
        **overrides,
    }


def _market_data_client(catalogs: dict[str, list[dict]]) -> MagicMock:
    client = MagicMock()
    client.get_catalog.side_effect = lambda asset_class: catalogs.get(asset_class, [])
    return client


def test_build_global_markets_merges_catalog_data_for_a_published_ticker() -> None:
    client = _market_data_client(
        {"future": [_catalog_row("GOLD", type="future", current_price=2440.3, currency="USD")]}
    )

    rows = build_global_markets(client)

    gold = next(r for r in rows if r["ticker"] == "GOLD")
    assert gold["asset_class"] == "future"
    assert gold["name"] == "GOLD Inc."  # catalog's own name wins
    assert gold["current_price"] == 2440.3
    assert gold["currency"] == "USD"


def test_build_global_markets_falls_back_to_configured_name_when_unpublished() -> None:
    client = _market_data_client({})  # nothing published for any asset class

    rows = build_global_markets(client)

    assert len(rows) == len(GLOBAL_MARKETS_ENTRIES)
    gold = next(r for r in rows if r["ticker"] == "GOLD")
    assert gold["name"] == "Gold"  # GLOBAL_MARKETS_ENTRIES' own fallback name
    assert gold["current_price"] is None
    assert gold["currency"] is None


def test_build_global_markets_only_reads_fx_future_benchmark_catalogs() -> None:
    client = _market_data_client({})

    build_global_markets(client)

    called_with = {call.args[0] for call in client.get_catalog.call_args_list}
    assert called_with == {"fx", "future", "benchmark"}


def test_build_global_markets_preserves_configured_order() -> None:
    client = _market_data_client({})

    rows = build_global_markets(client)

    assert [r["ticker"] for r in rows] == [e["ticker"] for e in GLOBAL_MARKETS_ENTRIES]


def test_stock_etf_catalog_rows_tags_asset_class_and_reads_only_stock_and_etf() -> None:
    client = _market_data_client(
        {
            "stock": [_catalog_row("AAPL", type="stock")],
            "etf": [_catalog_row("VOO", type="etf")],
            "fx": [_catalog_row("EURUSD", type="fx")],
        }
    )

    rows = stock_etf_catalog_rows(client)

    assert {r["ticker"]: r["asset_class"] for r in rows} == {"AAPL": "stock", "VOO": "etf"}
    called_with = {call.args[0] for call in client.get_catalog.call_args_list}
    assert called_with == {"stock", "etf"}


def test_build_top_movers_winners_keeps_only_positive_cagr_highest_first() -> None:
    rows = [
        {**_catalog_row("A"), "asset_class": "stock", "cagr_1y": 0.05},
        {**_catalog_row("B"), "asset_class": "stock", "cagr_1y": 0.30},
        {**_catalog_row("C"), "asset_class": "etf", "cagr_1y": -0.10},
        {**_catalog_row("D"), "asset_class": "stock", "cagr_1y": None},
    ]

    winners = build_top_movers(rows, "winners", limit=50)

    assert [w["ticker"] for w in winners] == ["B", "A"]
    assert winners[0]["change_1y_pct"] == 30.0


def test_build_top_movers_losers_keeps_only_negative_cagr_lowest_first() -> None:
    rows = [
        {**_catalog_row("A"), "asset_class": "stock", "cagr_1y": -0.05},
        {**_catalog_row("B"), "asset_class": "stock", "cagr_1y": -0.30},
        {**_catalog_row("C"), "asset_class": "etf", "cagr_1y": 0.10},
    ]

    losers = build_top_movers(rows, "losers", limit=50)

    assert [l["ticker"] for l in losers] == ["B", "A"]
    assert losers[0]["change_1y_pct"] == -30.0


def test_build_top_movers_respects_limit() -> None:
    rows = [{**_catalog_row(f"T{i}"), "asset_class": "stock", "cagr_1y": float(i)} for i in range(1, 6)]

    winners = build_top_movers(rows, "winners", limit=2)

    assert [w["ticker"] for w in winners] == ["T5", "T4"]


def test_build_account_movers_dedupes_by_ticker_and_excludes_non_stock_etf() -> None:
    stock_etf_rows = [{**_catalog_row("AAPL"), "asset_class": "stock", "cagr_1y": 0.2}]
    account_pie_holdings = [
        {"ticker": "AAPL", "asset_class": "stock", "account_id": "acc-1"},
        {"ticker": "AAPL", "asset_class": "stock", "pie_id": "pie-1"},  # duplicate ticker
        {"ticker": "GBPUSD", "asset_class": "fx", "account_id": "acc-1"},  # wrong asset class
    ]
    enrich = MagicMock(side_effect=lambda holdings: [{**h, "name": "Apple Inc."} for h in holdings])

    result = build_account_movers(stock_etf_rows, "winners", 50, account_pie_holdings, enrich)

    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert result[0]["change_1y_pct"] == 20.0
    enrich.assert_called_once()
    assert len(enrich.call_args.args[0]) == 1  # only one deduplicated holding passed through


def test_build_account_movers_excludes_holdings_with_no_matching_or_qualifying_catalog_row() -> None:
    stock_etf_rows = [
        {**_catalog_row("AAPL"), "asset_class": "stock", "cagr_1y": 0.2},
        {**_catalog_row("MSFT"), "asset_class": "stock", "cagr_1y": None},  # no CAGR yet
    ]
    account_pie_holdings = [
        {"ticker": "AAPL", "asset_class": "stock", "account_id": "acc-1"},
        {"ticker": "MSFT", "asset_class": "stock", "account_id": "acc-1"},
        {"ticker": "TSLA", "asset_class": "stock", "account_id": "acc-1"},  # not in catalog at all
    ]
    enrich = MagicMock(side_effect=lambda holdings: holdings)

    result = build_account_movers(stock_etf_rows, "winners", 50, account_pie_holdings, enrich)

    assert [r["ticker"] for r in result] == ["AAPL"]


def test_build_account_movers_orders_by_ranking_not_holdings_order() -> None:
    stock_etf_rows = [
        {**_catalog_row("A"), "asset_class": "stock", "cagr_1y": 0.05},
        {**_catalog_row("B"), "asset_class": "stock", "cagr_1y": 0.30},
    ]
    account_pie_holdings = [
        {"ticker": "A", "asset_class": "stock", "account_id": "acc-1"},
        {"ticker": "B", "asset_class": "stock", "account_id": "acc-1"},
    ]
    enrich = MagicMock(side_effect=lambda holdings: holdings)

    result = build_account_movers(stock_etf_rows, "winners", 50, account_pie_holdings, enrich)

    assert [r["ticker"] for r in result] == ["B", "A"]
