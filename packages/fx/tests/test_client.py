from unittest.mock import MagicMock

from equicast_fx.client import FXClient


def _datafeed(info: dict) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    return datafeed


def test_symbol_is_uppercase_yfinance_fx_ticker() -> None:
    client = FXClient("gbp", "usd", datafeed=_datafeed({}))
    assert client.symbol == "GBPUSD=X"


def test_profile_maps_yfinance_info_fields() -> None:
    info = {
        "exchange": "CCY",
        "region": "US",
        "longName": "GBP/USD",
        "regularMarketTime": 1787952545,
    }
    client = FXClient("GBP", "USD", datafeed=_datafeed(info))

    profile = client.profile()

    assert profile == {
        "from_currency": "GBP",
        "to_currency": "USD",
        "exchange": "CCY",
        "region": "US",
        "description": "GBP/USD",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }


def test_profile_falls_back_to_short_name_and_current_time() -> None:
    info = {"exchange": "CCY", "region": "US", "shortName": "GBP/USD"}
    client = FXClient("GBP", "USD", datafeed=_datafeed(info))

    profile = client.profile()

    assert profile["description"] == "GBP/USD"
    assert profile["last_updated"]
    assert profile["source"] == "yfinance"
