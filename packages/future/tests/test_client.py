import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER
from equicast_datafeed.disclaimers import reset_warned
from equicast_future.client import FutureClient


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


_FULL_INFO = {
    "exchange": "CMX",
    "region": None,
    "longName": "Gold",
    "currency": "USD",
    "regularMarketTime": 1787952545,
    "regularMarketOpen": 2410.5,
    "regularMarketDayHigh": 2455.2,
    "regularMarketDayLow": 2398.1,
    "regularMarketPrice": 2440.3,
    "fiftyTwoWeekHigh": 2500.8,
    "fiftyTwoWeekLow": 1900.4,
}

_HISTORY = pd.DataFrame({"Open": [2100.0, 2150.0, 2410.5]})


def _datafeed(info: dict, history: pd.DataFrame = _HISTORY) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_history.return_value = history
    return datafeed


def test_key_is_uppercased_but_symbol_is_kept_as_is() -> None:
    client = FutureClient("gold", "GC=F", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.key == "GOLD"
    assert client.symbol == "GC=F"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        FutureClient("GOLD", "GC=F", datafeed=_datafeed({}, pd.DataFrame()))
        FutureClient("SILVER", "SI=F", datafeed=_datafeed({}, pd.DataFrame()))

    assert caplog.messages == [YFINANCE_DATA_DISCLAIMER]


def test_profile_maps_yfinance_info_fields() -> None:
    client = FutureClient("GOLD", "GC=F", datafeed=_datafeed(_FULL_INFO))

    profile = client.profile()

    assert profile == {
        "key": "GOLD",
        "symbol": "GC=F",
        "name": "Gold",
        "exchange": "CMX",
        "currency": "USD",
        "region": None,
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
        "day_open": 2410.5,
        "day_high": 2455.2,
        "day_low": 2398.1,
        "day_close": 2440.3,
        "year_open": 2100.0,
        "year_high": 2500.8,
        "year_low": 1900.4,
        "year_close": 2440.3,
    }


def test_profile_year_open_is_first_row_of_history() -> None:
    history = pd.DataFrame({"Open": [1800.0, 1850.0, 1900.0]})
    client = FutureClient("GOLD", "GC=F", datafeed=_datafeed(_FULL_INFO, history))

    assert client.profile()["year_open"] == 1800.0


def test_profile_year_open_is_none_when_history_is_empty() -> None:
    client = FutureClient("GOLD", "GC=F", datafeed=_datafeed(_FULL_INFO, pd.DataFrame()))

    assert client.profile()["year_open"] is None


def test_profile_falls_back_to_short_name_and_current_time() -> None:
    info = {"exchange": "CMX", "region": None, "shortName": "Gold"}
    client = FutureClient("GOLD", "GC=F", datafeed=_datafeed(info, pd.DataFrame()))

    profile = client.profile()

    assert profile["name"] == "Gold"
    assert profile["last_updated"]
    assert profile["source"] == "yfinance"


_PRICE_HISTORY = pd.DataFrame(
    {
        "Open": [2400.0, 2410.0],
        "High": [2420.0, 2430.0],
        "Low": [2390.0, 2400.0],
        "Close": [2410.0, 2420.0],
    },
    index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
)


def test_prices_returns_one_record_per_row() -> None:
    datafeed = _datafeed({"currency": "USD"}, _PRICE_HISTORY)
    client = FutureClient("GOLD", "GC=F", datafeed=datafeed)

    records = client.prices()

    assert records == [
        {
            "key": "GOLD",
            "symbol": "GC=F",
            "currency": "USD",
            "date": "2026-01-02",
            "open": 2400.0,
            "high": 2420.0,
            "low": 2390.0,
            "close": 2410.0,
            "average": round((2390.0 + 2420.0) / 2, 8),
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        },
        {
            "key": "GOLD",
            "symbol": "GC=F",
            "currency": "USD",
            "date": "2026-01-05",
            "open": 2410.0,
            "high": 2430.0,
            "low": 2400.0,
            "close": 2420.0,
            "average": round((2400.0 + 2430.0) / 2, 8),
            "last_updated": records[1]["last_updated"],
            "source": "yfinance",
        },
    ]
    assert records[0]["last_updated"] == records[1]["last_updated"]


def test_prices_currency_is_none_when_yfinance_has_none() -> None:
    client = FutureClient("GOLD", "GC=F", datafeed=_datafeed({}, _PRICE_HISTORY))

    records = client.prices()

    assert all(record["currency"] is None for record in records)


def test_prices_default_uses_ytd_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    FutureClient("GOLD", "GC=F", datafeed=datafeed).prices()

    datafeed.get_history.assert_called_once_with("GC=F", period="ytd")


def test_prices_full_load_uses_max_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    FutureClient("GOLD", "GC=F", datafeed=datafeed).prices(full_load=True)

    datafeed.get_history.assert_called_once_with("GC=F", period="max")


def test_prices_empty_history_returns_no_records() -> None:
    client = FutureClient("GOLD", "GC=F", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.prices() == []
