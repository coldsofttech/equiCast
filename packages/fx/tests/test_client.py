from unittest.mock import MagicMock

import pandas as pd
from equicast_fx.client import FXClient

_FULL_INFO = {
    "exchange": "CCY",
    "region": "US",
    "longName": "GBP/USD",
    "regularMarketTime": 1787952545,
    "regularMarketOpen": 1.3594,
    "regularMarketDayHigh": 1.3598,
    "regularMarketDayLow": 1.3527,
    "regularMarketPrice": 1.3537,
    "fiftyTwoWeekHigh": 1.3847,
    "fiftyTwoWeekLow": 1.3012,
    "fiftyDayAverage": 1.3417,
    "twoHundredDayAverage": 1.3431,
}

_HISTORY = pd.DataFrame({"Open": [1.35, 1.351, 1.3594]})


def _datafeed(info: dict, history: pd.DataFrame = _HISTORY) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_history.return_value = history
    return datafeed


def test_symbol_is_uppercase_yfinance_fx_ticker() -> None:
    client = FXClient("gbp", "usd", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.symbol == "GBPUSD=X"


def test_profile_maps_yfinance_info_fields() -> None:
    client = FXClient("GBP", "USD", datafeed=_datafeed(_FULL_INFO))

    profile = client.profile()

    assert profile == {
        "from_currency": "GBP",
        "to_currency": "USD",
        "exchange": "CCY",
        "region": "US",
        "description": "GBP/USD",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
        "day_open": 1.3594,
        "day_high": 1.3598,
        "day_low": 1.3527,
        "day_close": 1.3537,
        "day_average": (1.3527 + 1.3598) / 2,
        "year_open": 1.35,
        "year_high": 1.3847,
        "year_low": 1.3012,
        "year_close": 1.3537,
        "year_average": (1.3012 + 1.3847) / 2,
        "moving_average_50_days": 1.3417,
        "moving_average_200_days": 1.3431,
    }


def test_profile_year_open_is_first_row_of_history() -> None:
    history = pd.DataFrame({"Open": [1.10, 1.20, 1.30]})
    client = FXClient("GBP", "USD", datafeed=_datafeed(_FULL_INFO, history))

    assert client.profile()["year_open"] == 1.10


def test_profile_year_open_is_none_when_history_is_empty() -> None:
    client = FXClient("GBP", "USD", datafeed=_datafeed(_FULL_INFO, pd.DataFrame()))

    assert client.profile()["year_open"] is None


def test_profile_averages_are_none_when_high_or_low_missing() -> None:
    info = {"exchange": "CCY", "region": "US", "shortName": "GBP/USD"}
    client = FXClient("GBP", "USD", datafeed=_datafeed(info, pd.DataFrame()))

    profile = client.profile()

    assert profile["day_average"] is None
    assert profile["year_average"] is None


def test_profile_falls_back_to_short_name_and_current_time() -> None:
    info = {"exchange": "CCY", "region": "US", "shortName": "GBP/USD"}
    client = FXClient("GBP", "USD", datafeed=_datafeed(info, pd.DataFrame()))

    profile = client.profile()

    assert profile["description"] == "GBP/USD"
    assert profile["last_updated"]
    assert profile["source"] == "yfinance"


_PRICE_HISTORY = pd.DataFrame(
    {
        "Open": [1.30, 1.31],
        "High": [1.32, 1.33],
        "Low": [1.29, 1.30],
        "Close": [1.31, 1.32],
    },
    index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
)


def test_prices_returns_one_record_per_row() -> None:
    client = FXClient("GBP", "USD", datafeed=_datafeed({}, _PRICE_HISTORY))

    records = client.prices()

    assert records == [
        {
            "from_currency": "GBP",
            "to_currency": "USD",
            "date": "2026-01-02",
            "open": 1.30,
            "high": 1.32,
            "low": 1.29,
            "close": 1.31,
            "average": round((1.29 + 1.32) / 2, 8),
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        },
        {
            "from_currency": "GBP",
            "to_currency": "USD",
            "date": "2026-01-05",
            "open": 1.31,
            "high": 1.33,
            "low": 1.30,
            "close": 1.32,
            "average": round((1.30 + 1.33) / 2, 8),
            "last_updated": records[1]["last_updated"],
            "source": "yfinance",
        },
    ]
    assert records[0]["last_updated"] == records[1]["last_updated"]


def test_prices_default_uses_ytd_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    FXClient("GBP", "USD", datafeed=datafeed).prices()

    datafeed.get_history.assert_called_once_with("GBPUSD=X", period="ytd")


def test_prices_full_load_uses_max_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    FXClient("GBP", "USD", datafeed=datafeed).prices(full_load=True)

    datafeed.get_history.assert_called_once_with("GBPUSD=X", period="max")


def test_prices_empty_history_returns_no_records() -> None:
    client = FXClient("GBP", "USD", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.prices() == []
