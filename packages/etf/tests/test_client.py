import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER
from equicast_datafeed.disclaimers import reset_warned
from equicast_etf.client import ETFClient


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


_FULL_INFO = {
    "longName": "Vanguard S&P 500 ETF",
    "quoteType": "ETF",
    "exchange": "PCX",
    "currency": "USD",
    "longBusinessSummary": "Tracks the performance of the S&P 500 Index.",
    "category": "Large Blend",
    "fundFamily": "Vanguard",
    "beta3Year": 1.0,
    "netExpenseRatio": 0.03,
    "trailingAnnualDividendRate": 5.66,
    "yield": 0.0107,
    "totalAssets": 1686884319232,
    "navPrice": 708.98,
    "volume": 8067208,
    "regularMarketOpen": 709.39,
    "regularMarketDayHigh": 712.6692,
    "regularMarketDayLow": 706.26,
    "regularMarketPrice": 707.24,
    "fiftyTwoWeekHigh": 716.39,
    "fiftyTwoWeekLow": 578.46,
    "fiftyDayAverage": 693.1996,
    "twoHundredDayAverage": 652.7322,
    "ytdReturn": 10.11602,
    "threeYearAverageReturn": 0.2217858,
    "fiveYearAverageReturn": 0.1294499,
    "fundInceptionDate": 1283817600,
    "regularMarketTime": 1787947200,
}


_HISTORY = pd.DataFrame({"Open": [588.29, 600.0, 709.39]})


def _datafeed(info: dict, history: pd.DataFrame = _HISTORY) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_history.return_value = history
    return datafeed


def test_symbol_is_uppercase_ticker_no_suffix() -> None:
    client = ETFClient("voo", datafeed=_datafeed({}))
    assert client.symbol == "VOO"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        ETFClient("VOO", datafeed=_datafeed({}))
        ETFClient("QQQ", datafeed=_datafeed({}))

    assert caplog.messages == [YFINANCE_DATA_DISCLAIMER]


def test_profile_maps_yfinance_info_fields() -> None:
    client = ETFClient("VOO", datafeed=_datafeed(_FULL_INFO))

    profile = client.profile()

    assert profile == {
        "ticker": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "quote_type": "ETF",
        "exchange": "PCX",
        "currency": "USD",
        "description": "Tracks the performance of the S&P 500 Index.",
        "category": "Large Blend",
        "fund_family": "Vanguard",
        "website": "https://www.vanguard.com",
        "beta": 1.0,
        "expense_ratio": 0.03,
        "dividend_rate": 5.66,
        "dividend_yield": 0.0107,
        "total_assets": 1686884319232,
        "nav_price": 708.98,
        "volume": 8067208,
        "day_open": 709.39,
        "day_high": 712.6692,
        "day_low": 706.26,
        "day_close": 707.24,
        "day_average": 709.4646,
        "year_open": 588.29,
        "year_high": 716.39,
        "year_low": 578.46,
        "year_close": 707.24,
        "year_average": 647.425,
        "moving_average_50_days": 693.1996,
        "moving_average_200_days": 652.7322,
        "ytd_return": 10.11602,
        "three_year_average_return": 0.2217858,
        "five_year_average_return": 0.1294499,
        "inception_date": "2010-09-07T00:00:00+00:00",
        "last_updated": "2026-08-28T20:00:00+00:00",
        "source": "yfinance",
    }


def test_profile_falls_back_to_short_name_and_current_time() -> None:
    info = {"shortName": "VOO"}
    client = ETFClient("VOO", datafeed=_datafeed(info))

    profile = client.profile()

    assert profile["name"] == "VOO"
    assert profile["last_updated"]
    assert profile["source"] == "yfinance"


def test_profile_dividend_and_fund_fields_are_none_when_unavailable() -> None:
    client = ETFClient("VOO", datafeed=_datafeed({}))

    profile = client.profile()

    assert profile["dividend_rate"] is None
    assert profile["dividend_yield"] is None
    assert profile["expense_ratio"] is None
    assert profile["total_assets"] is None
    assert profile["nav_price"] is None
    assert profile["category"] is None
    assert profile["fund_family"] is None
    assert profile["website"] is None
    assert profile["beta"] is None
    assert profile["ytd_return"] is None
    assert profile["three_year_average_return"] is None
    assert profile["five_year_average_return"] is None


def test_profile_volume_falls_back_to_regular_market_volume() -> None:
    info = {"regularMarketVolume": 12345}
    client = ETFClient("VOO", datafeed=_datafeed(info))

    assert client.profile()["volume"] == 12345


def test_profile_fetches_history_over_the_trailing_year() -> None:
    datafeed = _datafeed({})
    ETFClient("VOO", datafeed=datafeed).profile()

    datafeed.get_history.assert_called_once_with("VOO", period="1y")


def test_profile_year_open_is_first_row_of_history() -> None:
    history = pd.DataFrame({"Open": [10.0, 20.0, 30.0]})
    client = ETFClient("VOO", datafeed=_datafeed({}, history))

    assert client.profile()["year_open"] == 10.0


def test_profile_year_open_is_none_when_history_is_empty() -> None:
    client = ETFClient("VOO", datafeed=_datafeed({}, pd.DataFrame()))

    assert client.profile()["year_open"] is None


def test_profile_day_and_year_averages_are_none_when_high_or_low_missing() -> None:
    client = ETFClient("VOO", datafeed=_datafeed({}, pd.DataFrame()))

    profile = client.profile()

    assert profile["day_average"] is None
    assert profile["year_average"] is None


@pytest.mark.parametrize(
    ("fund_family", "expected_website"),
    [
        ("Vanguard", "https://www.vanguard.com"),
        ("iShares", "https://www.ishares.com"),
        ("BlackRock Asset Management Ireland - ETF", "https://www.ishares.com"),
        ("Invesco", "https://www.invesco.com"),
        ("State Street Investment Management", "https://www.ssga.com"),
        ("Schwab ETFs", "https://www.schwabassetmanagement.com"),
        ("Some Unknown Issuer", None),
        (None, None),
    ],
)
def test_profile_website_from_fund_family(fund_family, expected_website) -> None:
    info = {"fundFamily": fund_family} if fund_family is not None else {}
    client = ETFClient("VOO", datafeed=_datafeed(info))

    assert client.profile()["website"] == expected_website


def test_profile_inception_date_falls_back_to_first_trade_date_milliseconds() -> None:
    info = {"firstTradeDateMilliseconds": 968716800000}
    client = ETFClient("VOO", datafeed=_datafeed(info))

    assert client.profile()["inception_date"] == "2000-09-12T00:00:00+00:00"


def test_profile_inception_date_falls_back_to_epoch_utc_seconds() -> None:
    info = {"firstTradeDateEpochUtc": 968716800}
    client = ETFClient("VOO", datafeed=_datafeed(info))

    assert client.profile()["inception_date"] == "2000-09-12T00:00:00+00:00"


def test_profile_inception_date_is_none_when_unavailable() -> None:
    client = ETFClient("VOO", datafeed=_datafeed({}))

    assert client.profile()["inception_date"] is None


_PRICE_HISTORY = pd.DataFrame(
    {
        "Open": [700.10, 705.20],
        "High": [702.50, 707.80],
        "Low": [698.00, 703.90],
        "Close": [701.30, 706.10],
    },
    index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
)


def test_prices_returns_one_record_per_row() -> None:
    client = ETFClient("VOO", datafeed=_datafeed({"currency": "USD"}, _PRICE_HISTORY))

    records = client.prices()

    assert records == [
        {
            "ticker": "VOO",
            "currency": "USD",
            "date": "2026-01-02",
            "open": 700.10,
            "high": 702.50,
            "low": 698.00,
            "close": 701.30,
            "average": round((698.00 + 702.50) / 2, 8),
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        },
        {
            "ticker": "VOO",
            "currency": "USD",
            "date": "2026-01-05",
            "open": 705.20,
            "high": 707.80,
            "low": 703.90,
            "close": 706.10,
            "average": round((703.90 + 707.80) / 2, 8),
            "last_updated": records[1]["last_updated"],
            "source": "yfinance",
        },
    ]
    assert records[0]["last_updated"] == records[1]["last_updated"]


def test_prices_default_uses_ytd_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    ETFClient("VOO", datafeed=datafeed).prices()

    datafeed.get_history.assert_called_once_with("VOO", period="ytd")


def test_prices_full_load_uses_max_period() -> None:
    datafeed = _datafeed({}, _PRICE_HISTORY)
    ETFClient("VOO", datafeed=datafeed).prices(full_load=True)

    datafeed.get_history.assert_called_once_with("VOO", period="max")


def test_prices_empty_history_returns_no_records() -> None:
    client = ETFClient("VOO", datafeed=_datafeed({}, pd.DataFrame()))
    assert client.prices() == []
