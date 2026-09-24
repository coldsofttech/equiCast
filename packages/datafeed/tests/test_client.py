import logging
import threading
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


def test_get_news_returns_list_and_passes_count_through() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.get_news.return_value = [{"id": "abc"}]

        result = _client().get_news("AAPL", count=10)

    mock_ticker.assert_called_once_with("AAPL")
    mock_ticker.return_value.get_news.assert_called_once_with(count=10, tab="news")
    assert result == [{"id": "abc"}]


def test_get_news_passes_tab_through() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.get_news.return_value = [{"id": "abc"}]

        _client().get_news("AAPL", count=10, tab="all")

    mock_ticker.return_value.get_news.assert_called_once_with(count=10, tab="all")


def test_get_news_cache_is_keyed_by_tab() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.get_news.side_effect = [
            [{"id": "latest"}],
            [{"id": "all"}],
        ]
        client = _client()

        news_tab = client.get_news("AAPL", tab="news")
        all_tab = client.get_news("AAPL", tab="all")

    assert news_tab == [{"id": "latest"}]
    assert all_tab == [{"id": "all"}]
    assert mock_ticker.return_value.get_news.call_count == 2


def test_get_info_is_cached_within_one_client() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"exchange": "CCY"}
        client = _client()

        first = client.get_info("GBPUSD=X")
        second = client.get_info("GBPUSD=X")

    mock_ticker.assert_called_once_with("GBPUSD=X")
    assert first == second == {"exchange": "CCY"}


def test_get_history_cache_is_keyed_by_period_and_interval() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.side_effect = ["one-year", "year-to-date"]
        client = _client()

        one_year = client.get_history("AAPL", period="1y", interval="1d")
        ytd = client.get_history("AAPL", period="ytd", interval="1d")

    # Different periods are genuinely different data, so both must still hit
    # yfinance - only a call identical in every argument should be cached.
    assert mock_ticker.return_value.history.call_count == 2
    assert (one_year, ytd) == ("one-year", "year-to-date")


def test_cache_does_not_span_separate_client_instances() -> None:
    with patch("equicast_datafeed.client.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"exchange": "CCY"}
        _client().get_info("GBPUSD=X")
        _client().get_info("GBPUSD=X")

    assert mock_ticker.call_count == 2


def test_failed_fetch_is_cached_and_not_retried_by_a_later_call() -> None:
    with patch(
        "equicast_datafeed.client.yf.Ticker", side_effect=ConnectionError("boom")
    ) as mock_ticker:
        client = _client()
        with pytest.raises(DatafeedError):
            client.get_info("GBPUSD=X")
        calls_for_first_failure = mock_ticker.call_count

        with pytest.raises(DatafeedError):
            client.get_info("GBPUSD=X")

    # The second call re-raises the cached error instead of re-running the
    # whole retry-with-backoff sequence against yfinance again.
    assert mock_ticker.call_count == calls_for_first_failure


def test_concurrent_first_requests_for_the_same_key_fetch_only_once() -> None:
    call_count = 0
    started = threading.Event()
    release = threading.Event()

    def slow_ticker(_symbol: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        started.set()
        release.wait(timeout=5)
        return MagicMock(info={"exchange": "CCY"})

    with patch("equicast_datafeed.client.yf.Ticker", side_effect=slow_ticker):
        client = _client()
        results: list[dict] = []

        def worker() -> None:
            results.append(client.get_info("GBPUSD=X"))

        first = threading.Thread(target=worker)
        first.start()
        assert started.wait(timeout=5), "first thread never reached the fetch"

        second = threading.Thread(target=worker)
        second.start()
        release.set()
        first.join(timeout=5)
        second.join(timeout=5)

    # The second thread arrived while the first was still mid-fetch for the
    # same key - it must block on that in-flight fetch and reuse its result,
    # not race it and trigger a second yfinance call.
    assert call_count == 1
    assert results == [{"exchange": "CCY"}, {"exchange": "CCY"}]


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        _client()
        _client()

    assert caplog.messages == [YFINANCE_DATA_DISCLAIMER]
