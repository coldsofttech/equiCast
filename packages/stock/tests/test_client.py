import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER
from equicast_datafeed.disclaimers import reset_warned
from equicast_stock.client import StockClient


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


_FULL_INFO = {
    "longName": "Apple Inc.",
    "quoteType": "EQUITY",
    "exchange": "NMS",
    "currency": "USD",
    "longBusinessSummary": "Apple Inc. designs, manufactures, and markets smartphones.",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "website": "https://www.apple.com",
    "beta": 1.2,
    "payoutRatio": 0.15,
    "dividendRate": 1.0,
    "dividendYield": 0.005,
    "marketCap": 3000000000000,
    "volume": 50000000,
    "regularMarketOpen": 227.5,
    "regularMarketDayHigh": 229.10,
    "regularMarketDayLow": 226.80,
    "regularMarketPrice": 228.50,
    "fiftyTwoWeekHigh": 260.10,
    "fiftyTwoWeekLow": 164.08,
    "fiftyDayAverage": 220.45,
    "twoHundredDayAverage": 200.12,
    "address1": "One Apple Park Way",
    "city": "Cupertino",
    "state": "CA",
    "zip": "95014",
    "country": "United States",
    "region": "North America",
    "fullTimeEmployees": 164000,
    "companyOfficers": [
        {"name": "Timothy D. Cook", "title": "CEO & Director"},
        {"name": "Luca Maestri", "title": "CFO"},
    ],
    "firstTradeDateMilliseconds": 345479400000,
    "regularMarketTime": 1787952545,
}


_HISTORY = pd.DataFrame({"Open": [180.0, 181.5, 227.5]})


def _datafeed(info: dict, history: pd.DataFrame = _HISTORY) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_history.return_value = history
    return datafeed


def test_symbol_is_uppercase_ticker_no_suffix() -> None:
    client = StockClient("aapl", datafeed=_datafeed({}))
    assert client.symbol == "AAPL"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        StockClient("AAPL", datafeed=_datafeed({}))
        StockClient("MSFT", datafeed=_datafeed({}))

    assert caplog.messages == [YFINANCE_DATA_DISCLAIMER]


def test_profile_maps_yfinance_info_fields() -> None:
    client = StockClient("AAPL", datafeed=_datafeed(_FULL_INFO))

    profile = client.profile()

    assert profile == {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "quote_type": "EQUITY",
        "exchange": "NMS",
        "currency": "USD",
        "description": "Apple Inc. designs, manufactures, and markets smartphones.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "website": "https://www.apple.com",
        "beta": 1.2,
        "payout_ratio": 0.15,
        "dividend_rate": 1.0,
        "dividend_yield": 0.005,
        "market_cap": 3000000000000,
        "volume": 50000000,
        "day_open": 227.5,
        "day_high": 229.1,
        "day_low": 226.8,
        "day_close": 228.5,
        "day_average": 227.95,
        "year_open": 180.0,
        "year_high": 260.1,
        "year_low": 164.08,
        "year_close": 228.5,
        "year_average": 212.09,
        "moving_average_50_days": 220.45,
        "moving_average_200_days": 200.12,
        "address": "One Apple Park Way, Cupertino, CA 95014",
        "country": "United States",
        "region": "North America",
        "full_time_employees": 164000,
        "ceos": [{"name": "Timothy D. Cook", "role": "CEO & Director"}],
        "ipo_date": "1980-12-12T14:30:00+00:00",
        "last_updated": "2026-08-28T21:29:05+00:00",
        "source": "yfinance",
    }


def test_profile_falls_back_to_short_name_and_current_time() -> None:
    info = {"shortName": "Apple"}
    client = StockClient("AAPL", datafeed=_datafeed(info))

    profile = client.profile()

    assert profile["name"] == "Apple"
    assert profile["last_updated"]
    assert profile["source"] == "yfinance"


def test_profile_dividend_fields_are_none_when_not_a_dividend_payer() -> None:
    client = StockClient("AAPL", datafeed=_datafeed({}))

    profile = client.profile()

    assert profile["payout_ratio"] is None
    assert profile["dividend_rate"] is None
    assert profile["dividend_yield"] is None


def test_profile_volume_falls_back_to_regular_market_volume() -> None:
    info = {"regularMarketVolume": 12345}
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["volume"] == 12345


def test_profile_fetches_history_over_the_trailing_year() -> None:
    datafeed = _datafeed({})
    StockClient("AAPL", datafeed=datafeed).profile()

    datafeed.get_history.assert_called_once_with("AAPL", period="1y")


def test_profile_year_open_is_first_row_of_history() -> None:
    history = pd.DataFrame({"Open": [10.0, 20.0, 30.0]})
    client = StockClient("AAPL", datafeed=_datafeed({}, history))

    assert client.profile()["year_open"] == 10.0


def test_profile_year_open_is_none_when_history_is_empty() -> None:
    client = StockClient("AAPL", datafeed=_datafeed({}, pd.DataFrame()))

    assert client.profile()["year_open"] is None


def test_profile_day_and_year_averages_are_none_when_high_or_low_missing() -> None:
    client = StockClient("AAPL", datafeed=_datafeed({}, pd.DataFrame()))

    profile = client.profile()

    assert profile["day_average"] is None
    assert profile["year_average"] is None


def test_profile_address_formats_all_parts() -> None:
    info = {"address1": "One Apple Park Way", "city": "Cupertino", "state": "CA", "zip": "95014"}
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["address"] == "One Apple Park Way, Cupertino, CA 95014"


def test_profile_address_handles_missing_state_and_zip() -> None:
    info = {"address1": "1 Some Street", "city": "London", "country": "United Kingdom"}
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["address"] == "1 Some Street, London"


def test_profile_address_is_none_when_unavailable() -> None:
    client = StockClient("AAPL", datafeed=_datafeed({}))
    assert client.profile()["address"] is None


def test_profile_ceos_includes_co_ceos_and_excludes_non_ceo_officers() -> None:
    info = {
        "companyOfficers": [
            {"name": "Officer A", "title": "Co-CEO"},
            {"name": "Officer B", "title": "Co-CEO"},
            {"name": "Officer C", "title": "CFO"},
        ]
    }
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["ceos"] == [
        {"name": "Officer A", "role": "Co-CEO"},
        {"name": "Officer B", "role": "Co-CEO"},
    ]


def test_profile_ceos_from_officers_or_executive_team_use_their_actual_title_as_role() -> None:
    info = {
        "companyOfficers": [{"name": "Officer A", "title": "Chairman, President and CEO"}],
    }
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["ceos"] == [
        {"name": "Officer A", "role": "Chairman, President and CEO"}
    ]


def test_profile_ceos_falls_back_to_executive_team_when_no_officers_match() -> None:
    info = {
        "companyOfficers": [{"name": "Officer C", "title": "CFO"}],
        "executiveTeam": [{"name": "Officer D", "title": "Chief Executive Officer"}],
    }
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["ceos"] == [{"name": "Officer D", "role": "Chief Executive Officer"}]


def test_profile_ceos_falls_back_to_business_summary_pattern_match() -> None:
    info = {
        "longBusinessSummary": (
            "The company was founded in 1976. Timothy D. Cook serves as Chief "
            "Executive Officer and is a member of the board."
        )
    }
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["ceos"] == [{"name": "Timothy D. Cook", "role": "CEO"}]


def test_profile_ceos_business_summary_matches_name_after_title() -> None:
    info = {"longBusinessSummary": "Chief Executive Officer Timothy D. Cook leads the company."}
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["ceos"] == [{"name": "Timothy D. Cook", "role": "CEO"}]


def test_profile_ceos_empty_when_no_source_has_a_match() -> None:
    client = StockClient("AAPL", datafeed=_datafeed({}))
    assert client.profile()["ceos"] == []


def test_profile_ipo_date_falls_back_to_epoch_utc_seconds() -> None:
    info = {"firstTradeDateEpochUtc": 345479400}
    client = StockClient("AAPL", datafeed=_datafeed(info))

    assert client.profile()["ipo_date"] == "1980-12-12T14:30:00+00:00"


def test_profile_ipo_date_is_none_when_unavailable() -> None:
    client = StockClient("AAPL", datafeed=_datafeed({}))
    assert client.profile()["ipo_date"] is None
