import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_benchmark.client import BenchmarkClient
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER
from equicast_datafeed.disclaimers import reset_warned


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


_FULL_INFO = {
    "exchange": "SNP",
    "region": "US",
    "longName": "S&P 500",
    "currency": "USD",
    "regularMarketTime": 1787952545,
    "regularMarketOpen": 6410.5,
    "regularMarketDayHigh": 6455.2,
    "regularMarketDayLow": 6398.1,
    "regularMarketPrice": 6440.3,
    "fiftyTwoWeekHigh": 6500.8,
    "fiftyTwoWeekLow": 5200.4,
}

_HISTORY = pd.DataFrame({"Open": [6100.0, 6150.0, 6410.5]})


def _datafeed(info: dict, history: pd.DataFrame = _HISTORY) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_history.return_value = history
    return datafeed


def test_key_is_uppercased_but_symbol_is_kept_as_is() -> None:
    client = BenchmarkClient("sp500", "^GSPC", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.key == "SP500"
    assert client.symbol == "^GSPC"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed({}, pd.DataFrame()))
        BenchmarkClient("FTSE100", "^FTSE", datafeed=_datafeed({}, pd.DataFrame()))

    assert caplog.messages == [YFINANCE_DATA_DISCLAIMER]


def test_profile_maps_yfinance_info_fields() -> None:
    client = BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed(_FULL_INFO))

    profile = client.profile()

    assert profile == {
        "key": "SP500",
        "symbol": "^GSPC",
        "name": "S&P 500",
        "exchange": "SNP",
        "currency": "USD",
        "region": "US",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
        "day_open": 6410.5,
        "day_high": 6455.2,
        "day_low": 6398.1,
        "day_close": 6440.3,
        "year_open": 6100.0,
        "year_high": 6500.8,
        "year_low": 5200.4,
        "year_close": 6440.3,
    }


def test_profile_year_open_is_first_row_of_history() -> None:
    history = pd.DataFrame({"Open": [5000.0, 5100.0, 5200.0]})
    client = BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed(_FULL_INFO, history))

    assert client.profile()["year_open"] == 5000.0


def test_profile_year_open_is_none_when_history_is_empty() -> None:
    client = BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed(_FULL_INFO, pd.DataFrame()))

    assert client.profile()["year_open"] is None


def test_profile_falls_back_to_short_name_and_current_time() -> None:
    info = {"exchange": "SNP", "region": "US", "shortName": "S&P 500"}
    client = BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed(info, pd.DataFrame()))

    profile = client.profile()

    assert profile["name"] == "S&P 500"
    assert profile["last_updated"]
    assert profile["source"] == "yfinance"


_PRICE_HISTORY = pd.DataFrame(
    {
        "Open": [6400.0, 6410.0],
        "High": [6420.0, 6430.0],
        "Low": [6390.0, 6400.0],
        "Close": [6410.0, 6420.0],
    },
    index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
)


def test_prices_returns_one_record_per_row() -> None:
    datafeed = _datafeed({"currency": "USD"}, _PRICE_HISTORY)
    client = BenchmarkClient("SP500", "^GSPC", datafeed=datafeed)

    records = client.prices()

    assert records == [
        {
            "key": "SP500",
            "symbol": "^GSPC",
            "currency": "USD",
            "date": "2026-01-02",
            "open": 6400.0,
            "high": 6420.0,
            "low": 6390.0,
            "close": 6410.0,
            "average": round((6390.0 + 6420.0) / 2, 8),
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        },
        {
            "key": "SP500",
            "symbol": "^GSPC",
            "currency": "USD",
            "date": "2026-01-05",
            "open": 6410.0,
            "high": 6430.0,
            "low": 6400.0,
            "close": 6420.0,
            "average": round((6400.0 + 6430.0) / 2, 8),
            "last_updated": records[1]["last_updated"],
            "source": "yfinance",
        },
    ]
    assert records[0]["last_updated"] == records[1]["last_updated"]


def test_prices_currency_is_none_when_yfinance_has_none() -> None:
    client = BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed({}, _PRICE_HISTORY))

    records = client.prices()

    assert all(record["currency"] is None for record in records)


def test_prices_default_uses_ytd_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    BenchmarkClient("SP500", "^GSPC", datafeed=datafeed).prices()

    datafeed.get_history.assert_called_once_with("^GSPC", period="ytd")


def test_prices_full_load_uses_max_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    BenchmarkClient("SP500", "^GSPC", datafeed=datafeed).prices(full_load=True)

    datafeed.get_history.assert_called_once_with("^GSPC", period="max")


def test_prices_empty_history_returns_no_records() -> None:
    client = BenchmarkClient("SP500", "^GSPC", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.prices() == []
