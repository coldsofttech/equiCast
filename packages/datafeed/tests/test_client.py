import logging
from unittest.mock import MagicMock, patch

import pytest
from equicast_datafeed.client import DatafeedClient
from equicast_datafeed.disclaimers import YFINANCE_DATA_DISCLAIMER, reset_warned
from equicast_datafeed.exceptions import DatafeedError


@pytest.fixture(autouse=True)
def _no_rate_limit_sleep():
    with patch("equicast_datafeed.rate_limit.time.sleep"):
        yield


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


def _client() -> DatafeedClient:
    return DatafeedClient(
        max_calls=100, period_seconds=1.0, max_retries=3, backoff_base_seconds=0.0
    )


def test_get_info_returns_ticker_info() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"exchange": "CCY", "region": "US"}

        result = _client().get_info("GBPUSD=X")

    mock_ticker.assert_called_once_with("GBPUSD=X")
    assert result == {"exchange": "CCY", "region": "US"}


def test_get_info_retries_then_succeeds() -> None:
    good_ticker = MagicMock(info={"exchange": "CCY"})
    responses = iter([ConnectionError("boom"), good_ticker])

    def ticker_side_effect(_symbol: str) -> MagicMock:
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    with patch("equicast_datafeed.client.yf.Ticker", side_effect=ticker_side_effect):
        result = _client().get_info("GBPUSD=X")

    assert result == {"exchange": "CCY"}


def test_get_info_raises_datafeed_error_after_exhausting_retries() -> None:
    with patch("equicast_datafeed.client.yf.Ticker", side_effect=ConnectionError("boom")):
        with pytest.raises(DatafeedError):
            _client().get_info("GBPUSD=X")


def test_get_history_returns_dataframe() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = "not-really-a-dataframe"

        result = _client().get_history("GBPUSD=X", period="1y", interval="1d")

    mock_ticker.return_value.history.assert_called_once_with(period="1y", interval="1d")
    assert result == "not-really-a-dataframe"


def test_get_dividends_returns_series() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.dividends = "not-really-a-series"

        result = _client().get_dividends("AAPL")

    mock_ticker.assert_called_once_with("AAPL")
    assert result == "not-really-a-series"


def test_get_balance_sheet_returns_dataframe() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.balance_sheet = "not-really-a-dataframe"

        result = _client().get_balance_sheet("AAPL")

    mock_ticker.assert_called_once_with("AAPL")
    assert result == "not-really-a-dataframe"


def test_get_financials_returns_dataframe() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.financials = "not-really-a-dataframe"

        result = _client().get_financials("AAPL")

    mock_ticker.assert_called_once_with("AAPL")
    assert result == "not-really-a-dataframe"


def test_get_earnings_dates_returns_dataframe() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.get_earnings_dates.return_value = "not-really-a-dataframe"

        result = _client().get_earnings_dates("AAPL", limit=8)

    mock_ticker.assert_called_once_with("AAPL")
    mock_ticker.return_value.get_earnings_dates.assert_called_once_with(limit=8)
    assert result == "not-really-a-dataframe"


def test_get_upgrades_downgrades_returns_dataframe() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.upgrades_downgrades = "not-really-a-dataframe"

        result = _client().get_upgrades_downgrades("AAPL")

    mock_ticker.assert_called_once_with("AAPL")
    assert result == "not-really-a-dataframe"


def test_get_splits_returns_series() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.splits = "not-really-a-series"

        result = _client().get_splits("AAPL")

    mock_ticker.assert_called_once_with("AAPL")
    assert result == "not-really-a-series"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        _client()
        _client()

    assert caplog.messages == [YFINANCE_DATA_DISCLAIMER]
