from pathlib import Path
from unittest.mock import MagicMock, patch

from equicast_watchlist.config import WatchlistEntry
from equicast_watchlist.movers import (
    TickerCagr,
    compute_cagr_rankings,
    load_rankings,
    merge_change_1y,
    select_top,
    to_watchlist_entries,
    write_rankings,
)


def _write_yaml(path: Path, tickers: list[str]) -> Path:
    if not tickers:
        path.write_text("tickers: []\n")
        return path
    path.write_text("tickers:\n" + "\n".join(f"  - {t}" for t in tickers))
    return path


def test_compute_cagr_rankings_covers_stock_then_etf_tickers_in_order(tmp_path: Path) -> None:
    stock_config = _write_yaml(tmp_path / "stocks.yaml", ["AAPL", "MSFT"])
    etf_config = _write_yaml(tmp_path / "etfs.yaml", ["VOO"])

    with patch("equicast_watchlist.movers.MetricsClient") as mock_metrics_client:
        mock_metrics_client.return_value.metrics.side_effect = [
            {"cagr_1y": 0.2},
            {"cagr_1y": -0.1},
            {"cagr_1y": None},
        ]

        rankings = compute_cagr_rankings(stock_config, etf_config, MagicMock())

    assert rankings == [
        TickerCagr(asset_class="stock", ticker="AAPL", cagr_1y=0.2),
        TickerCagr(asset_class="stock", ticker="MSFT", cagr_1y=-0.1),
        TickerCagr(asset_class="etf", ticker="VOO", cagr_1y=None),
    ]


def test_compute_cagr_rankings_preserves_order_with_multiple_workers(tmp_path: Path) -> None:
    stock_config = _write_yaml(tmp_path / "stocks.yaml", [f"T{i}" for i in range(10)])
    etf_config = _write_yaml(tmp_path / "etfs.yaml", [])

    def fake_metrics_client(ticker, datafeed=None):
        client = MagicMock()
        client.metrics.return_value = {"cagr_1y": float(ticker[1:])}
        return client

    with patch("equicast_watchlist.movers.MetricsClient", side_effect=fake_metrics_client):
        rankings = compute_cagr_rankings(stock_config, etf_config, MagicMock(), max_workers=4)

    assert [r.ticker for r in rankings] == [f"T{i}" for i in range(10)]


def test_write_and_load_rankings_round_trips(tmp_path: Path) -> None:
    rankings = [
        TickerCagr(asset_class="stock", ticker="AAPL", cagr_1y=0.2),
        TickerCagr(asset_class="etf", ticker="VOO", cagr_1y=None),
    ]
    path = write_rankings(rankings, tmp_path / "out" / "rankings.json")

    assert load_rankings(path) == rankings


def test_select_top_winners_keeps_only_positive_cagr_highest_first() -> None:
    rankings = [
        TickerCagr(asset_class="stock", ticker="A", cagr_1y=0.05),
        TickerCagr(asset_class="stock", ticker="B", cagr_1y=0.30),
        TickerCagr(asset_class="stock", ticker="C", cagr_1y=-0.10),
        TickerCagr(asset_class="stock", ticker="D", cagr_1y=None),
        TickerCagr(asset_class="stock", ticker="E", cagr_1y=0.0),
    ]

    selected = select_top(rankings, "winners", limit=50)

    assert [r.ticker for r in selected] == ["B", "A"]


def test_select_top_losers_keeps_only_negative_cagr_lowest_first() -> None:
    rankings = [
        TickerCagr(asset_class="stock", ticker="A", cagr_1y=-0.05),
        TickerCagr(asset_class="stock", ticker="B", cagr_1y=-0.30),
        TickerCagr(asset_class="stock", ticker="C", cagr_1y=0.10),
        TickerCagr(asset_class="stock", ticker="D", cagr_1y=None),
    ]

    selected = select_top(rankings, "losers", limit=50)

    assert [r.ticker for r in selected] == ["B", "A"]


def test_select_top_respects_limit() -> None:
    rankings = [
        TickerCagr(asset_class="stock", ticker=f"T{i}", cagr_1y=float(i)) for i in range(1, 6)
    ]

    selected = select_top(rankings, "winners", limit=2)

    assert [r.ticker for r in selected] == ["T5", "T4"]


def test_to_watchlist_entries_builds_one_entry_per_selected_ticker() -> None:
    selected = [
        TickerCagr(asset_class="stock", ticker="AAPL", cagr_1y=0.2),
        TickerCagr(asset_class="etf", ticker="VOO", cagr_1y=0.1),
    ]

    entries = to_watchlist_entries(selected)

    assert entries == [
        WatchlistEntry(asset_class="stock", ticker="AAPL", name="AAPL"),
        WatchlistEntry(asset_class="etf", ticker="VOO", name="VOO"),
    ]


def test_merge_change_1y_converts_cagr_fraction_to_percent() -> None:
    selected = [
        TickerCagr(asset_class="stock", ticker="AAPL", cagr_1y=0.2),
        TickerCagr(asset_class="stock", ticker="MSFT", cagr_1y=None),
    ]
    rows = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]

    merged = merge_change_1y(rows, selected)

    assert merged[0]["change_1y_pct"] == 20.0
    assert merged[1]["change_1y_pct"] is None
