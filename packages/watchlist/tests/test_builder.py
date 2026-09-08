from unittest.mock import MagicMock, patch

import pandas as pd
from equicast_watchlist.builder import build_entries, build_entry
from equicast_watchlist.config import WatchlistEntry

FX_ENTRY = WatchlistEntry(
    asset_class="fx", ticker="EURUSD", name="EUR/USD", from_currency="EUR", to_currency="USD"
)
FUTURE_ENTRY = WatchlistEntry(
    asset_class="future", ticker="GOLD", name="Gold", key="GOLD", symbol="GC=F"
)
BENCHMARK_ENTRY = WatchlistEntry(
    asset_class="benchmark", ticker="SP500", name="S&P 500", key="SP500", symbol="^GSPC"
)

#: 21 ascending daily closes: enough for both the 5-trading-day-back "week"
#: reference and a full "month" (oldest row) reference.
_HISTORY = pd.DataFrame(
    {
        "Open": [100.0 + i for i in range(21)],
        "High": [101.0 + i for i in range(21)],
        "Low": [99.0 + i for i in range(21)],
        "Close": [100.0 + i for i in range(21)],
    },
    index=pd.date_range("2026-01-01", periods=21, freq="D"),
)


def _datafeed(history: pd.DataFrame = _HISTORY) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_history.return_value = history
    return datafeed


def test_build_entry_for_future_uses_future_client() -> None:
    datafeed = _datafeed()
    with patch("equicast_watchlist.builder.FutureClient") as mock_future_client:
        mock_client = mock_future_client.return_value
        mock_client.symbol = "GC=F"
        mock_client.profile.return_value = {
            "name": "Gold",
            "currency": "USD",
            "day_close": 2440.3,
            "last_updated": "2026-08-28T21:29:05+00:00",
        }

        row = build_entry(FUTURE_ENTRY, datafeed)

    mock_future_client.assert_called_once_with("GOLD", "GC=F", datafeed=datafeed)
    assert row["asset_class"] == "future"
    assert row["ticker"] == "GOLD"
    assert row["symbol"] == "GC=F"
    assert row["name"] == "Gold"
    assert row["currency"] == "USD"
    assert row["current_price"] == 2440.3
    assert row["source"] == "yfinance"


def test_build_entry_for_fx_uses_fx_client_and_to_currency_fallback() -> None:
    datafeed = _datafeed()
    with patch("equicast_watchlist.builder.FXClient") as mock_fx_client:
        mock_client = mock_fx_client.return_value
        mock_client.symbol = "EURUSD=X"
        mock_client.profile.return_value = {
            "description": "EUR/USD",
            "to_currency": "USD",
            "day_close": 1.08,
            "last_updated": "2026-08-28T21:29:05+00:00",
        }

        row = build_entry(FX_ENTRY, datafeed)

    mock_fx_client.assert_called_once_with("EUR", "USD", datafeed=datafeed)
    assert row["name"] == "EUR/USD"  # falls back to description
    assert row["currency"] == "USD"  # falls back to to_currency
    assert row["current_price"] == 1.08


def test_build_entry_for_benchmark_uses_benchmark_client() -> None:
    datafeed = _datafeed()
    with patch("equicast_watchlist.builder.BenchmarkClient") as mock_benchmark_client:
        mock_client = mock_benchmark_client.return_value
        mock_client.symbol = "^GSPC"
        mock_client.profile.return_value = {
            "name": "S&P 500",
            "currency": "USD",
            "day_close": 6440.3,
            "last_updated": "2026-08-28T21:29:05+00:00",
        }

        row = build_entry(BENCHMARK_ENTRY, datafeed)

    mock_benchmark_client.assert_called_once_with("SP500", "^GSPC", datafeed=datafeed)
    assert row["name"] == "S&P 500"


def test_build_entry_falls_back_to_config_name_when_profile_has_none() -> None:
    datafeed = _datafeed()
    with patch("equicast_watchlist.builder.FutureClient") as mock_future_client:
        mock_client = mock_future_client.return_value
        mock_client.symbol = "GC=F"
        mock_client.profile.return_value = {"day_close": 2440.3, "last_updated": "x"}

        row = build_entry(FUTURE_ENTRY, datafeed)

    assert row["name"] == "Gold"  # entry.name, not None


def test_build_entry_computes_week_and_month_change() -> None:
    datafeed = _datafeed()
    with patch("equicast_watchlist.builder.FutureClient") as mock_future_client:
        mock_client = mock_future_client.return_value
        mock_client.symbol = "GC=F"
        # current_price (120.0) vs close 5 trading days back (index -6 = 115.0)
        # and the oldest close in the 21-row window (100.0).
        mock_client.profile.return_value = {
            "name": "Gold",
            "currency": "USD",
            "day_close": 120.0,
            "last_updated": "x",
        }

        row = build_entry(FUTURE_ENTRY, datafeed)

    assert row["change_1w_pct"] == round((120.0 - 115.0) / 115.0 * 100, 8)
    assert row["change_1m_pct"] == round((120.0 - 100.0) / 100.0 * 100, 8)


def test_build_entry_change_is_none_without_enough_history() -> None:
    datafeed = _datafeed(pd.DataFrame({"Open": [], "High": [], "Low": [], "Close": []}))
    with patch("equicast_watchlist.builder.FutureClient") as mock_future_client:
        mock_client = mock_future_client.return_value
        mock_client.symbol = "GC=F"
        mock_client.profile.return_value = {
            "name": "Gold",
            "currency": "USD",
            "day_close": 120.0,
            "last_updated": "x",
        }

        row = build_entry(FUTURE_ENTRY, datafeed)

    assert row["change_1w_pct"] is None
    assert row["change_1m_pct"] is None


def test_build_entry_change_is_none_when_current_price_is_none() -> None:
    datafeed = _datafeed()
    with patch("equicast_watchlist.builder.FutureClient") as mock_future_client:
        mock_client = mock_future_client.return_value
        mock_client.symbol = "GC=F"
        mock_client.profile.return_value = {
            "name": "Gold",
            "currency": "USD",
            "day_close": None,
            "last_updated": "x",
        }

        row = build_entry(FUTURE_ENTRY, datafeed)

    assert row["current_price"] is None
    assert row["change_1w_pct"] is None
    assert row["change_1m_pct"] is None


def test_build_entries_preserves_config_order_with_multiple_workers() -> None:
    datafeed = _datafeed()

    def fake_client(key, symbol, datafeed=None):
        client = MagicMock()
        client.symbol = symbol
        client.profile.return_value = {
            "name": key,
            "currency": "USD",
            "day_close": 1.0,
            "last_updated": "x",
        }
        return client

    entries = [
        WatchlistEntry(
            asset_class="future", ticker=f"F{i}", name=f"F{i}", key=f"F{i}", symbol=f"F{i}=F"
        )
        for i in range(10)
    ]

    with patch("equicast_watchlist.builder.FutureClient", side_effect=fake_client):
        rows = build_entries(entries, datafeed, max_workers=4)

    assert [row["ticker"] for row in rows] == [f"F{i}" for i in range(10)]
