import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest
from equicast_datafeed import YFINANCE_DATA_DISCLAIMER, DatafeedClient
from equicast_datafeed.disclaimers import reset_warned
from equicast_dividends.client import EQUICAST_DIVIDENDS_DISCLAIMER, DividendsClient


@pytest.fixture(autouse=True)
def _reset_disclaimer():
    reset_warned()
    yield
    reset_warned()


def _dividends_series(entries: list[tuple[str, float]]) -> pd.Series:
    index = pd.DatetimeIndex([date for date, _ in entries]).tz_localize("UTC")
    return pd.Series([amount for _, amount in entries], index=index)


def _datafeed(info: dict, dividends: pd.Series) -> MagicMock:
    datafeed = MagicMock()
    datafeed.get_info.return_value = info
    datafeed.get_dividends.return_value = dividends
    return datafeed


def test_symbol_is_uppercased() -> None:
    client = DividendsClient("aapl", datafeed=_datafeed({}, pd.Series(dtype=float)))
    assert client.symbol == "AAPL"


def test_constructing_client_shows_yfinance_disclaimer_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        DividendsClient("AAPL", datafeed=_datafeed({}, pd.Series(dtype=float)))
        DividendsClient("MSFT", datafeed=_datafeed({}, pd.Series(dtype=float)))

    assert caplog.messages == [EQUICAST_DIVIDENDS_DISCLAIMER]


def test_dividends_disclaimer_is_not_deduped_by_datafeeds_own_disclaimer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # DividendsClient's message is distinct from equicast-datafeed's, so it
    # still shows even when the datafeed's own disclaimer already fired
    # earlier in the process (e.g. DatafeedClient constructed first in
    # equicast-stock's CLI).
    with caplog.at_level(logging.WARNING):
        DatafeedClient()
        DividendsClient("AAPL", datafeed=_datafeed({}, pd.Series(dtype=float)))

    assert YFINANCE_DATA_DISCLAIMER in caplog.messages
    assert EQUICAST_DIVIDENDS_DISCLAIMER in caplog.messages


def test_dividends_returns_one_record_per_ex_dividend_date() -> None:
    this_year = datetime.now(UTC).year
    dividends = _dividends_series([(f"{this_year}-02-10", 0.26), (f"{this_year}-05-12", 0.27)])
    client = DividendsClient("AAPL", datafeed=_datafeed({"currency": "USD"}, dividends))

    records = client.dividends()

    assert records == [
        {
            "ticker": "AAPL",
            "currency": "USD",
            "ex_dividend_date": f"{this_year}-02-10",
            "price": 0.26,
            "last_updated": records[0]["last_updated"],
            "source": "yfinance",
        },
        {
            "ticker": "AAPL",
            "currency": "USD",
            "ex_dividend_date": f"{this_year}-05-12",
            "price": 0.27,
            "last_updated": records[1]["last_updated"],
            "source": "yfinance",
        },
    ]
    assert records[0]["last_updated"] == records[1]["last_updated"]


def test_dividends_default_excludes_prior_years() -> None:
    this_year = datetime.now(UTC).year
    dividends = _dividends_series([(f"{this_year - 1}-11-10", 0.25), (f"{this_year}-02-10", 0.26)])
    client = DividendsClient("AAPL", datafeed=_datafeed({}, dividends))

    records = client.dividends()

    assert [r["ex_dividend_date"] for r in records] == [f"{this_year}-02-10"]


def test_dividends_default_includes_future_dated_entries() -> None:
    # Default is year-to-date *and beyond* (`index.year >= this year`, not
    # `== this year`) - a no-op in practice since yfinance's dividend data
    # has no forward-looking entries (see DividendsClient.dividends()'s
    # docstring), but this locks in the filter's intended direction rather
    # than relying on that absence.
    this_year = datetime.now(UTC).year
    dividends = _dividends_series([(f"{this_year}-02-10", 0.26), (f"{this_year + 1}-01-15", 0.27)])
    client = DividendsClient("AAPL", datafeed=_datafeed({}, dividends))

    records = client.dividends()

    assert [r["ex_dividend_date"] for r in records] == [
        f"{this_year}-02-10",
        f"{this_year + 1}-01-15",
    ]


def test_dividends_full_load_returns_every_year() -> None:
    this_year = datetime.now(UTC).year
    dividends = _dividends_series([(f"{this_year - 1}-11-10", 0.25), (f"{this_year}-02-10", 0.26)])
    client = DividendsClient("AAPL", datafeed=_datafeed({}, dividends))

    records = client.dividends(full_load=True)

    assert [r["ex_dividend_date"] for r in records] == [
        f"{this_year - 1}-11-10",
        f"{this_year}-02-10",
    ]


def test_dividends_empty_series_returns_no_records() -> None:
    client = DividendsClient("TSLA", datafeed=_datafeed({}, pd.Series(dtype=float)))
    assert client.dividends() == []
