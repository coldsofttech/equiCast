from pathlib import Path

import pytest
from equicast_watchlist.config import WatchlistEntry, load_watchlist_entries


def test_load_watchlist_entries_parses_fx_future_and_benchmark_rows(tmp_path: Path) -> None:
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        """
        entries:
          - asset_class: fx
            from: eur
            to: usd
            name: EUR/USD
          - asset_class: future
            key: gold
            symbol: "GC=F"
            name: Gold
          - asset_class: benchmark
            key: sp500
            symbol: "^GSPC"
            name: S&P 500
        """
    )

    entries = load_watchlist_entries(config)

    assert entries == [
        WatchlistEntry(
            asset_class="fx",
            ticker="EURUSD",
            name="EUR/USD",
            from_currency="EUR",
            to_currency="USD",
        ),
        WatchlistEntry(
            asset_class="future", ticker="GOLD", name="Gold", key="GOLD", symbol="GC=F"
        ),
        WatchlistEntry(
            asset_class="benchmark", ticker="SP500", name="S&P 500", key="SP500", symbol="^GSPC"
        ),
    ]


def test_load_watchlist_entries_rejects_unknown_asset_class(tmp_path: Path) -> None:
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        """
        entries:
          - asset_class: stock
            key: AAPL
            symbol: AAPL
            name: Apple
        """
    )

    with pytest.raises(ValueError, match="Unknown asset_class"):
        load_watchlist_entries(config)
